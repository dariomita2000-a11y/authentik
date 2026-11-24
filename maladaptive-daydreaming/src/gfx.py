"""Low-level drawing helpers: masks, glows, silhouettes, grading. Frames are float32 HxWx3 in [0, 1+]."""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 720, 1280
SS = 2  # supersampling for silhouettes
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


def col(hexstr, k=1.0):
    h = hexstr.lstrip("#")
    return np.array([int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)], np.float32) * k


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def lerp(a, b, t):
    return a + (b - a) * t


def vgrad(stops):
    """stops: [(y_frac, color), ...] -> HxWx3"""
    ys = np.array([s[0] for s in stops], np.float32) * H
    cs = np.stack([s[1] for s in stops])
    y = np.arange(H, dtype=np.float32)
    out = np.stack([np.interp(y, ys, cs[:, c]) for c in range(3)], axis=1)
    return np.broadcast_to(out[:, None, :], (H, W, 3)).copy()


def glow(cx, cy, r, sx=1.0, sy=1.0):
    d2 = ((XX - cx) / sx) ** 2 + ((YY - cy) / sy) ** 2
    return np.exp(-d2 / (r * r)).astype(np.float32)


def add(img, mask, color, k=1.0):
    img += mask[..., None] * (color * k)[None, None, :]
    return img


def over(img, mask, color):
    m = mask[..., None]
    img *= 1 - m
    img += m * color[None, None, :]
    return img


def mask_from(draw_fn, blur=0.0):
    """Draw with PIL at SS x resolution (fill 255), return float mask HxW."""
    im = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(im)
    draw_fn(d, SS)
    im = im.resize((W, H), Image.BILINEAR)
    if blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, np.float32) / 255.0


def blur_arr(a, r):
    if r <= 0:
        return a
    if a.ndim == 2:
        im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), "L")
        return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0
    # float RGB blur via 16-bit-ish precision: scale down
    hdr = max(1.0, float(a.max()))
    im = Image.fromarray(np.clip(a / hdr * 255, 0, 255).astype(np.uint8), "RGB")
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0 * hdr


def blur_fast(a, r):
    """Blur by downscale -> blur -> upscale (for big radii)."""
    f = 4
    hdr = max(1.0, float(a.max()))
    im = Image.fromarray(np.clip(a / hdr * 255, 0, 255).astype(np.uint8), "RGB")
    small = im.resize((W // f, H // f), Image.BILINEAR).filter(ImageFilter.GaussianBlur(r / f))
    return np.asarray(small.resize((W, H), Image.BILINEAR), np.float32) / 255.0 * hdr


def shift(m, dx, dy):
    return np.roll(np.roll(m, int(dy), axis=0), int(dx), axis=1)


def rim(mask, dx, dy, blur=2.0):
    """Edge light: part of mask that disappears when shifted towards the light."""
    e = np.clip(mask - shift(mask, -dx, -dy), 0, 1)
    return blur_arr(e, blur) if blur else e


# ---------------------------------------------------------------- silhouettes


def _ell(d, box, **kw):
    x0, y0, x1, y1 = box
    d.ellipse([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], **kw)


def _limb(d, p0, p1, w0, w1=None):
    """Tapered capsule from p0 (width w0) to p1 (width w1)."""
    w1 = w0 if w1 is None else w1
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / L, dx / L
    r0, r1 = w0 / 2, w1 / 2
    d.polygon([(p0[0] + nx * r0, p0[1] + ny * r0), (p1[0] + nx * r1, p1[1] + ny * r1), (p1[0] - nx * r1, p1[1] - ny * r1), (p0[0] - nx * r0, p0[1] - ny * r0)], fill=255)
    _ell(d, [p0[0] - r0, p0[1] - r0, p0[0] + r0, p0[1] + r0], fill=255)
    _ell(d, [p1[0] - r1, p1[1] - r1, p1[0] + r1, p1[1] + r1], fill=255)


def _smooth_poly(d, pts, n=6):
    d.polygon(catmull(pts + [pts[0]], n), fill=255)


def person(d, s, x, ground, h, phase=0.0, facing=1, pose="walk", headphones=True, hair="short", gesture=0.0, walk_amt=1.0, view=None):
    """Human silhouette. view 'side' (walk/gesture/sit) or 'front' (standing, also reads as back view)."""
    if view is None:
        view = "front" if pose == "still" else "side"
    if view == "front":
        return person_front(d, s, x, ground, h, headphones=headphones, hair=hair, sway=math.sin(phase))
    U = h * s
    X = lambda v: (x + v * facing * h) * s  # noqa: E731
    Y = lambda v: (ground - v * h) * s  # noqa: E731
    bob = 0.007 * math.cos(phase * 2) * walk_amt
    lean = 0.012 * walk_amt
    sit = pose == "sit"
    hip_y = 0.06 if sit else 0.51
    sh_y = hip_y + 0.31
    hx = 0.0 if not sit else -0.02
    # torso (chest forward, back slightly curved, hoodie bulk)
    tor = [
        (X(hx - 0.060 + lean), Y(sh_y + 0.035 + bob)), (X(hx + 0.020 + lean), Y(sh_y + 0.045 + bob)), (X(hx + 0.075 + lean), Y(sh_y - 0.02 + bob)),
        (X(hx + 0.080 + lean * 0.5), Y(sh_y - 0.13 + bob)), (X(hx + 0.065), Y(hip_y + 0.03 + bob)), (X(hx + 0.055), Y(hip_y - 0.03 + bob)),
        (X(hx - 0.060), Y(hip_y - 0.035 + bob)), (X(hx - 0.075), Y(hip_y + 0.06 + bob)), (X(hx - 0.07 + lean * 0.5), Y(sh_y - 0.12 + bob)),
    ]
    _smooth_poly(d, tor)
    # neck & head
    hcx, hcy = X(hx + 0.012 + lean * 1.4), Y(sh_y + 0.125 + bob)
    _limb(d, (X(hx + 0.0 + lean), Y(sh_y + 0.01 + bob)), (X(hx + 0.012 + lean * 1.3), Y(sh_y + 0.08 + bob)), 0.052 * U)
    hr = 0.066 * U
    _ell(d, [hcx - hr * 0.98, hcy - hr * 1.12, hcx + hr * 0.98, hcy + hr * 0.92], fill=255)
    # face: nose + chin
    f = facing
    d.polygon([(hcx + f * hr * 0.78, hcy - hr * 0.2), (hcx + f * hr * 1.10, hcy + hr * 0.18), (hcx + f * hr * 0.92, hcy + hr * 0.32), (hcx + f * hr * 0.95, hcy + hr * 0.55), (hcx + f * hr * 0.6, hcy + hr * 0.95), (hcx, hcy + hr * 0.6)], fill=255)
    if hair == "long":
        sw = 0.010 * math.sin(phase * 0.7 + 0.5)
        _smooth_poly(d, [(hcx + f * hr * 0.5, hcy - hr * 1.1), (hcx - f * hr * 1.1, hcy - hr * 0.6), (X(hx - 0.085 - sw), Y(sh_y - 0.06 + bob)), (X(hx - 0.04 - sw), Y(sh_y - 0.05 + bob)), (hcx - f * hr * 0.1, hcy + hr * 0.3)])
    else:
        hc2 = hcx - f * hr * 0.12
        _ell(d, [hc2 - hr * 0.95, hcy - hr * 1.2, hc2 + hr * 0.95, hcy + hr * 0.15], fill=255)
    if headphones:
        bw = max(2, int(0.016 * U))
        d.arc([hcx - hr * 1.15, hcy - hr * 1.38, hcx + hr * 1.15, hcy + hr * 0.95], 195, 345, fill=255, width=bw)
        ex = hcx - f * hr * 0.12
        _ell(d, [ex - hr * 0.42, hcy - hr * 0.30, ex + hr * 0.42, hcy + hr * 0.55], fill=255)
    # legs
    hip = (X(hx + 0.0), Y(hip_y + bob))
    tl, sl = 0.245, 0.235
    for side in (0, 1):
        if sit:
            knee = (X(0.17 + side * 0.02), Y(0.30 - side * 0.015))
            foot = (X(0.29 + side * 0.03), Y(0.03))
        else:
            ph = phase + side * math.pi
            a = (0.40 * math.sin(ph)) * walk_amt + (0.02 * (side * 2 - 1) if walk_amt < 0.2 else 0)
            kb = (max(0.0, math.sin(ph + 1.3)) * 0.6 + 0.04) * walk_amt
            knee = (hip[0] + math.sin(a) * tl * U * facing, hip[1] + math.cos(a) * tl * U)
            a2 = a - kb
            foot = (knee[0] + math.sin(a2) * sl * U * facing, knee[1] + math.cos(a2) * sl * U)
        _limb(d, hip, knee, 0.092 * U, 0.066 * U)
        _limb(d, knee, foot, 0.064 * U, 0.044 * U)
        # shoe: heel behind, toe in front
        d.polygon([(foot[0] - f * 0.03 * U, foot[1] - 0.022 * U), (foot[0] + f * 0.075 * U, foot[1] + 0.002 * U), (foot[0] + f * 0.07 * U, foot[1] + 0.02 * U), (foot[0] - f * 0.035 * U, foot[1] + 0.02 * U)], fill=255)
    # arms
    shp = (X(hx + 0.002 + lean), Y(sh_y + bob))
    ua, fa = 0.165, 0.15
    for side in (0, 1):
        if pose == "gesture":
            g = gesture + side * 2.3
            s1, s2 = 0.5 + 0.5 * math.sin(g), 0.5 + 0.5 * math.sin(g * 1.37 + 0.8)
            if side == 0:
                a, a2 = 0.15 + 0.45 * s1, 0.15 + 0.45 * s1 + 0.9 + 0.7 * s2
            else:
                a, a2 = 0.05 + 0.2 * s1, 0.05 + 0.2 * s1 + 0.35 + 0.5 * s2
        elif sit:
            a, a2 = (0.55, 1.75) if side == 0 else (0.45, 1.6)
        else:
            a = -0.32 * math.sin(phase + side * math.pi) * walk_amt + 0.03
            a2 = a + 0.22 * walk_amt + 0.12
        el = (shp[0] + math.sin(a) * ua * U * facing, shp[1] + math.cos(a) * ua * U)
        hand = (el[0] + math.sin(a2) * fa * U * facing, el[1] + math.cos(a2) * fa * U)
        _limb(d, shp, el, 0.062 * U, 0.048 * U)
        _limb(d, el, hand, 0.046 * U, 0.036 * U)
        _ell(d, [hand[0] - 0.024 * U, hand[1] - 0.02 * U, hand[0] + 0.024 * U, hand[1] + 0.03 * U], fill=255)


def person_front(d, s, x, ground, h, headphones=False, hair="short", sway=0.0):
    U = h * s
    X = lambda v: (x + v * h) * s  # noqa: E731
    Y = lambda v: (ground - v * h) * s  # noqa: E731
    for m in (-1, 1):
        # leg
        _limb(d, (X(m * 0.052), Y(0.50)), (X(m * 0.048), Y(0.27)), 0.098 * U, 0.072 * U)
        _limb(d, (X(m * 0.048), Y(0.27)), (X(m * 0.045), Y(0.035)), 0.07 * U, 0.05 * U)
        _ell(d, [X(m * 0.045 - 0.03), Y(0.04), X(m * 0.045 + 0.03), Y(-0.005)], fill=255)
        # arm hanging, slightly away from body
        _limb(d, (X(m * 0.118), Y(0.79)), (X(m * 0.135), Y(0.63)), 0.06 * U, 0.05 * U)
        _limb(d, (X(m * 0.135), Y(0.63)), (X(m * 0.128), Y(0.47)), 0.048 * U, 0.04 * U)
        _ell(d, [X(m * 0.128 - 0.022), Y(0.49), X(m * 0.128 + 0.022), Y(0.43)], fill=255)
    torso = [(X(-0.03), Y(0.86)), (X(0.03), Y(0.86)), (X(0.115), Y(0.825)), (X(0.13), Y(0.78)), (X(0.105), Y(0.66)), (X(0.088), Y(0.57)),
             (X(0.098), Y(0.50)), (X(0.07), Y(0.45)), (X(-0.07), Y(0.45)), (X(-0.098), Y(0.50)), (X(-0.088), Y(0.57)), (X(-0.105), Y(0.66)), (X(-0.13), Y(0.78)), (X(-0.115), Y(0.825))]
    _smooth_poly(d, torso)
    _limb(d, (X(0), Y(0.83)), (X(0), Y(0.885)), 0.05 * U)
    hr = 0.062 * U
    hcx, hcy = X(0), Y(0.93)
    _ell(d, [hcx - hr * 0.88, hcy - hr * 1.12, hcx + hr * 0.88, hcy + hr * 1.0], fill=255)
    if hair == "long":
        sw = sway * 0.006 * U
        _smooth_poly(d, [(hcx - hr * 0.95, hcy - hr * 0.9), (hcx, hcy - hr * 1.25), (hcx + hr * 0.95, hcy - hr * 0.9), (hcx + hr * 1.25 + sw, Y(0.77)), (hcx + hr * 0.7 + sw, Y(0.75)), (hcx - hr * 0.7 + sw, Y(0.75)), (hcx - hr * 1.25 + sw, Y(0.77))])
    if headphones:
        bw = max(2, int(0.016 * U))
        d.arc([hcx - hr * 1.12, hcy - hr * 1.4, hcx + hr * 1.12, hcy + hr * 0.9], 180, 360, fill=255, width=bw)
        for m in (-1, 1):
            _ell(d, [hcx + m * hr * 0.95 - hr * 0.3, hcy - hr * 0.3, hcx + m * hr * 0.95 + hr * 0.3, hcy + hr * 0.5], fill=255)


def catmull(points, n=8):
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(
                tuple(
                    0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)
                    for j in range(2)
                )
            )
    out.append(points[-1])
    return out


# head-and-shoulders profile, facing +x, units: head height ~1, origin = ear
PROFILE = [
    (-1.45, 2.7), (-1.0, 1.82), (-0.55, 1.58), (-0.42, 1.38), (-0.40, 0.95), (-0.52, 0.45), (-0.50, 0.0), (-0.32, -0.36),
    (0.0, -0.5), (0.3, -0.42), (0.5, -0.2), (0.6, 0.05), (0.62, 0.2), (0.6, 0.3), (0.76, 0.5), (0.63, 0.57),
    (0.65, 0.66), (0.61, 0.7), (0.64, 0.76), (0.57, 0.85), (0.58, 0.95), (0.45, 1.05), (0.28, 1.08), (0.25, 1.3),
    (0.5, 1.55), (1.1, 1.8), (1.5, 2.7),
]
PROFILE_LONGHAIR = [
    (-1.45, 2.7), (-1.05, 1.95), (-0.98, 1.62), (-0.86, 1.15), (-0.8, 0.6), (-0.74, 0.1), (-0.55, -0.35), (-0.15, -0.6),
    (0.22, -0.56), (0.45, -0.38), (0.57, -0.15), (0.6, 0.05), (0.62, 0.2), (0.6, 0.3), (0.73, 0.5), (0.62, 0.57),
    (0.64, 0.66), (0.6, 0.7), (0.62, 0.76), (0.55, 0.85), (0.55, 0.94), (0.43, 1.02), (0.28, 1.05), (0.26, 1.3),
    (0.5, 1.55), (1.1, 1.8), (1.5, 2.7),
]


def profile(d, s, x, y, size, facing=1, kind="short", headphones=0.0, hp_lift=0.0, sway=0.0):
    """Close-up head profile. headphones: 0..1 visibility, hp_lift: px offset upward."""
    pts = PROFILE if kind == "short" else PROFILE_LONGHAIR
    poly = []
    for i, (px, py) in enumerate(catmull(pts, 10)):
        swx = sway * (max(0.0, py) * 0.08) * (1 if px < 0 else 0)
        poly.append(((x + (px + swx) * size * facing) * s, (y + py * size) * s))
    poly.append(((x + 1.5 * size * facing) * s, (H + 50) * s))
    poly.append(((x - 1.45 * size * facing) * s, (H + 50) * s))
    d.polygon(poly, fill=255)
    if headphones > 0:
        oy = -hp_lift
        bw = max(2, int(0.07 * size * s))
        c = int(255 * headphones)
        d.arc([(x - 0.62 * size) * s, (y - 0.68 * size + oy) * s, (x + 0.62 * size) * s, (y + 0.7 * size + oy) * s], 180, 360, fill=c, width=bw)
        ex = x - 0.02 * size * facing
        _ell(d, [(ex - 0.26 * size) * s, (y - 0.12 * size + oy) * s, (ex + 0.26 * size) * s, (y + 0.42 * size + oy) * s], fill=c)


# ---------------------------------------------------------------- finishing

_rng = np.random.default_rng(3)
GRAIN = [(_rng.normal(0, 1, (H, W)).astype(np.float32)) for _ in range(12)]


def finish(img, frame_idx, grain=0.035, vignette=0.55, bloom=0.35, warm=0.0, lift=0.012):
    img = np.maximum(img, 0)
    if bloom > 0:
        bright = np.clip(img - 0.55, 0, None)
        img = img + blur_fast(bright, 40) * bloom * 1.6 + blur_fast(bright, 12) * bloom * 0.6
    # vignette
    v = 1 - vignette * smooth(((XX - W / 2) ** 2 / (W * 0.75) ** 2 + (YY - H * 0.48) ** 2 / (H * 0.62) ** 2))
    img = img * v[..., None]
    # filmic tone curve
    img = img / (1 + img * 0.55) * 1.35
    # split tone: cool shadows, warm highlights
    lum = img.mean(axis=2, keepdims=True)
    shadow_tint = np.array([-0.012, 0.004, 0.022], np.float32)
    hi_tint = np.array([0.03, 0.012, -0.02], np.float32) * (1 + warm)
    img = img + (1 - np.clip(lum * 2, 0, 1)) * shadow_tint + np.clip(lum * 1.4 - 0.4, 0, 1) * hi_tint
    img = img * (1 - lift) + lift
    g = GRAIN[frame_idx % len(GRAIN)]
    img = img + g[..., None] * grain * (0.35 + 0.65 * np.sqrt(np.clip(1 - lum, 0, 1)))
    return np.clip(img, 0, 1)


def camera(img, zoom=1.0, cx=0.5, cy=0.5, rot=0.0):
    """Push-in / pan: crop around (cx, cy) by `zoom` (>=1) and resample back to W x H."""
    if zoom <= 1.0001 and abs(rot) < 1e-4:
        return img
    cw, ch = W / zoom, H / zoom
    x0 = min(max(cx * W - cw / 2, 0), W - cw)
    y0 = min(max(cy * H - ch / 2, 0), H - ch)
    chans = []
    for c in range(3):
        pil = Image.fromarray(np.ascontiguousarray(img[..., c], dtype=np.float32), "F")
        chans.append(np.asarray(pil.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BILINEAR), np.float32))
    return np.stack(chans, axis=2)
