"""Scene renderers. Each returns a float32 HxWx3 image (pre-grade) for local time t (seconds)."""

import math
from functools import lru_cache

import numpy as np

from gfx import (
    H, W, XX, YY, add, blur_arr, blur_fast, catmull, col, ease, glow, lerp, mask_from, over, person, profile, rim, smooth, vgrad,
)

DARK = col("#04060b")


# ---------------------------------------------------------------- particles & bokeh


def splat_disc(img, x, y, r, color, a, soft=0.25, ring=0.25):
    x0, x1 = int(max(0, x - r - 2)), int(min(W, x + r + 3))
    y0, y1 = int(max(0, y - r - 2)), int(min(H, y + r + 3))
    if x0 >= x1 or y0 >= y1:
        return
    d = np.sqrt((XX[y0:y1, x0:x1] - x) ** 2 + (YY[y0:y1, x0:x1] - y) ** 2) / max(r, 0.5)
    edge = np.clip((1 - d) / max(soft, 1e-3), 0, 1)
    m = edge * (1 - ring + ring * np.clip(d, 0, 1) ** 3)
    img[y0:y1, x0:x1] += m[..., None] * color[None, None, :] * a


def splat_glow(img, x, y, r, color, a):
    R = r * 3
    x0, x1 = int(max(0, x - R)), int(min(W, x + R + 1))
    y0, y1 = int(max(0, y - R)), int(min(H, y + R + 1))
    if x0 >= x1 or y0 >= y1:
        return
    d2 = ((XX[y0:y1, x0:x1] - x) ** 2 + (YY[y0:y1, x0:x1] - y) ** 2) / (r * r)
    img[y0:y1, x0:x1] += np.exp(-d2)[..., None] * color[None, None, :] * a


class Field:
    """Deterministic random particle set."""

    def __init__(self, n, seed, **ranges):
        rng = np.random.default_rng(seed)
        self.n = n
        for k, (lo, hi) in ranges.items():
            setattr(self, k, rng.uniform(lo, hi, n))


DUST = Field(140, 11, x=(0, 1), y=(0, 1), r=(0.6, 2.2), vx=(-4, 4), vy=(-6, 3), ph=(0, 6.28), a=(0.2, 1.0))


def dust(img, t, color, k=1.0, region=None, warm=False):
    for i in range(DUST.n):
        x = (DUST.x[i] * W + DUST.vx[i] * t + 10 * math.sin(t * 0.3 + DUST.ph[i])) % W
        y = (DUST.y[i] * H + DUST.vy[i] * t + 8 * math.cos(t * 0.25 + DUST.ph[i])) % H
        a = DUST.a[i] * (0.5 + 0.5 * math.sin(t * 0.8 + DUST.ph[i] * 3)) * k
        if region is not None:
            a *= float(region[int(y) % H, int(x) % W])
        if a > 0.02:
            splat_glow(img, x, y, DUST.r[i] * (1.6 if warm else 1.0), color, a * 0.5)


# ---------------------------------------------------------------- the room


WIN = (0.24 * W, 0.17 * H, 0.80 * W, 0.55 * H)  # x0 y0 x1 y1
GROUND = 0.865 * H


@lru_cache(maxsize=4)
def room_base(warm_q):
    warm = warm_q / 10.0
    img = vgrad([(0, col("#0a1020")), (0.6, col("#0a111f")), (0.78, col("#070b14")), (0.79, col("#0b111c")), (1, col("#06090f"))])
    x0, y0, x1, y1 = WIN
    # outside: moonlit sky vs dream sunset
    moon = vgrad([(0, col("#16243c")), (y0 / H, col("#1b2d4b")), (y1 / H, col("#4d6788")), (1, col("#4d6788"))])
    sun = vgrad([(0, col("#2a1a40")), (y0 / H, col("#3b2150")), ((y0 + y1) / 2 / H, col("#b25a5a")), (y1 / H, col("#f3a35c")), (1, col("#f3a35c"))])
    outside = moon * (1 - warm) + sun * warm
    # distant city glow & moon / sun
    outside += glow(x1 - 60, y0 + 70, 70)[..., None] * (col("#a9c4e6") * 0.5 * (1 - warm) + col("#ffd59a") * 0.0)
    outside += glow((x0 + x1) / 2, y1 + 10, 160, sy=0.5)[..., None] * (col("#ffb066") * 0.9 * warm)
    rng = np.random.default_rng(5)
    for _ in range(70):
        bx, by = rng.uniform(x0, x1), rng.uniform(y1 - 70, y1)
        c = col("#ffcf8a") if rng.random() < 0.7 else col("#bcd4ff")
        splat_glow(outside, bx, by, rng.uniform(1.0, 2.5), c, rng.uniform(0.2, 0.7) * (1 - 0.6 * warm))
    winmask = mask_from(lambda d, s: d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], fill=255), blur=0.8)
    img = img * (1 - winmask[..., None]) + outside * winmask[..., None]
    # mullions + frame
    mull = mask_from(
        lambda d, s: (
            d.rectangle([x0 * s - 10 * s, y0 * s - 10 * s, x1 * s + 10 * s, y0 * s + 6 * s], fill=255),
            d.rectangle([x0 * s - 10 * s, y1 * s - 6 * s, x1 * s + 10 * s, y1 * s + 14 * s], fill=255),
            d.rectangle([x0 * s - 10 * s, y0 * s, x0 * s + 6 * s, y1 * s], fill=255),
            d.rectangle([x1 * s - 6 * s, y0 * s, x1 * s + 10 * s, y1 * s], fill=255),
            d.rectangle([((x0 + x1) / 2 - 5) * s, y0 * s, ((x0 + x1) / 2 + 5) * s, y1 * s], fill=255),
            d.rectangle([x0 * s, ((y0 + y1) * 0.45 - 4) * s, x1 * s, ((y0 + y1) * 0.45 + 4) * s], fill=255),
        ),
        blur=0.6,
    )
    img = over(img, mull, col("#05080e"))
    # curtains
    curt = mask_from(
        lambda d, s: (
            d.polygon([(x0 - 70) * s, (y0 - 40) * s, (x0 + 25) * s, (y0 - 40) * s, (x0 + 5) * s, (GROUND - 10) * s, (x0 - 95) * s, (GROUND - 10) * s], fill=255),
            d.polygon([(x1 - 20) * s, (y0 - 40) * s, (x1 + 80) * s, (y0 - 40) * s, (x1 + 110) * s, (GROUND - 10) * s, (x1 + 5) * s, (GROUND - 10) * s], fill=255),
        ),
        blur=1.5,
    )
    folds = 0.55 + 0.45 * np.sin(XX * 0.11) ** 2
    lit = (glow(x0, (y0 + y1) / 2, 260, sy=1.8) + glow(x1, (y0 + y1) / 2, 260, sy=1.8)) * folds
    ccol = col("#0d1626") * (1 - warm) + col("#2a1712") * warm
    img = over(img, curt, ccol * 0.8)
    img = add(img, curt * lit, col("#40577a") * (1 - warm) + col("#c46a3a") * warm, 0.22)
    # bed (left) and a small desk lamp silhouette (right)
    bed = mask_from(
        lambda d, s: d.rounded_rectangle([-80 * s, (GROUND - 175) * s, (0.33 * W) * s, (H + 20) * s], radius=40 * s, fill=255), blur=1.2
    )
    img = over(img, bed, col("#070a11"))
    img = add(img, rim(bed, 0, -3, 2.0) * (glow(0.2 * W, GROUND - 170, 200)), col("#6c88b0") * (1 - warm) + col("#ff9a55") * warm, 0.35)
    # light shaft + floor pattern
    shaft = mask_from(
        lambda d, s: d.polygon([x0 * s, y0 * s, x1 * s, y0 * s, (x1 - 40) * s, (H + 40) * s, (x0 - 260) * s, (H + 40) * s], fill=255), blur=40
    )
    shaft *= smooth((YY - y0) / (H - y0)) * 0.9 + 0.1
    floor = mask_from(
        lambda d, s: d.polygon([(x0 - 40) * s, (GROUND - 8) * s, (x1 - 20) * s, (GROUND - 8) * s, (x1 - 120) * s, (H + 10) * s, (x0 - 320) * s, (H + 10) * s], fill=255),
        blur=10,
    )
    fl_shadow = mask_from(
        lambda d, s: (
            d.line([((x0 + x1) / 2 - 30) * s, (GROUND - 8) * s, ((x0 + x1) / 2 - 220) * s, (H + 10) * s], fill=255, width=14 * s),
            d.line([(x0 - 120) * s, (GROUND + 70) * s, (x1 - 60) * s, (GROUND + 70) * s], fill=255, width=10 * s),
        ),
        blur=6,
    )
    lc = col("#7d9bc7") * (1 - warm) + col("#ffad66") * warm
    img = add(img, shaft, lc, 0.085)
    img = add(img, floor * (1 - fl_shadow), lc, 0.28)
    img = add(img, glow((x0 + x1) / 2, (y0 + y1) / 2, 420), lc, 0.04)
    return img, shaft


def room(t, warm=0.0, figure="walk", fig_alpha=1.0, ghost=0.0, gesture=False, walk_speed=1.0, still_x=0.52, push=0.0, dusty=1.0, facing_still=1, light=1.0, hp=True, fig_h=0.43, ground=None, xr=(0.30, 0.70)):
    wq0 = int(math.floor(warm * 10))
    wq1 = min(10, wq0 + 1)
    f = warm * 10 - wq0
    b0, shaft = room_base(wq0)
    if f > 0.001:
        b1, _ = room_base(wq1)
        img = b0 * (1 - f) + b1 * f
    else:
        img = b0.copy()
    img *= light
    lc = col("#9bb5dc") * (1 - warm) + col("#ffc48a") * warm

    def figure_mask(tt, alpha):
        P = 7.6 / walk_speed
        xl, xr_ = xr[0] * W, xr[1] * W
        u = (tt / P) % 1.0
        legs = math.floor(tt / P) * 2
        if u < 0.5:
            k = smooth(u * 2)
            x, facing, legs_done = lerp(xl, xr_, k), 1, legs + k
        else:
            k = smooth((u - 0.5) * 2)
            x, facing, legs_done = lerp(xr_, xl, k), -1, legs + 1 + k
        sp = 6 * (k * (1 - k))  # 0 at ends
        hgt = fig_h * H
        gy = GROUND if ground is None else ground * H
        phase = legs_done * (xr_ - xl) / (0.26 * hgt) * math.pi
        if figure == "still":
            x, facing, sp, phase = still_x * W, facing_still, 0.0, 0.0
        if figure == "sit":
            return mask_from(lambda d, s: person(d, s, 0.29 * W, GROUND + 4, 0.40 * H, 0, 1, "sit", headphones=False), blur=0.9) * alpha
        pose = "gesture" if gesture else ("walk" if figure == "walk" else "still")
        return (
            mask_from(
                lambda d, s: person(d, s, x, gy, hgt, phase, facing, pose, headphones=hp, gesture=tt * 2.1, walk_amt=min(1.0, sp * 1.2) if figure == "walk" else 0.0),
                blur=0.9,
            )
            * alpha
        )

    if figure != "none":
        m = figure_mask(t, fig_alpha)
        if ghost > 0:
            for k, dt in enumerate((0.35, 0.7, 1.05)):
                g = figure_mask(t - dt, 1.0) * ghost * (0.45 - 0.12 * k)
                img = over(img, g * (1 - m), col("#0a0f19"))
        img = over(img, m, col("#03050a"))
        r = rim(m, 3, 0, 1.5) + rim(m, -3, 0, 1.5) + rim(m, 0, 3, 1.5) * 1.3
        img = add(img, r * glow((WIN[0] + WIN[2]) / 2, (WIN[1] + WIN[3]) / 2, 520), lc, 0.75 * light)
    if dusty > 0:
        dust(img, t, lc, 0.9 * dusty * light, region=np.clip(shaft * 1.4, 0, 1))
    return img


# ---------------------------------------------------------------- phone in the dark


def phone(t, progress=0.3, screen=1.0, tap=None, warm=0.0):
    img = vgrad([(0, col("#05070c")), (1, col("#080b12"))])
    cx, cy = 0.5 * W, 0.62 * H
    pw, ph = 190, 380
    ang = -8

    def ph_poly(d, s, inset=0):
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for px, py in ((-pw / 2 + inset, -ph / 2 + inset), (pw / 2 - inset, -ph / 2 + inset), (pw / 2 - inset, ph / 2 - inset), (-pw / 2 + inset, ph / 2 - inset)):
            pts.append(((cx + px * ca - py * sa) * s, (cy + px * sa + py * ca) * s))
        d.polygon(pts, fill=255)

    body = mask_from(lambda d, s: ph_poly(d, s), blur=1.2)
    scr = mask_from(lambda d, s: ph_poly(d, s, 9), blur=0.8)
    sc_col = col("#9fb7e0") * (1 - warm) + col("#ffc890") * warm
    # light spill on hand / bedsheet
    spill = glow(cx, cy, 330, sy=1.1)
    img = add(img, spill, sc_col, 0.16 * screen)
    # hand silhouette
    hand = mask_from(
        lambda d, s: (
            d.ellipse([(cx - 150) * s, (cy + 60) * s, (cx + 140) * s, (cy + 420) * s], fill=255),
            d.polygon([(cx - 140) * s, (cy + 200) * s, (cx + 120) * s, (cy + 200) * s, (cx + 200) * s, (H + 20) * s, (cx - 230) * s, (H + 20) * s], fill=255),
            d.rounded_rectangle([(cx + 70) * s, (cy - 40) * s, (cx + 118) * s, (cy + 150) * s], radius=24 * s, fill=255),
            d.rounded_rectangle([(cx - 125) * s, (cy - 10) * s, (cx - 80) * s, (cy + 160) * s], radius=22 * s, fill=255),
        ),
        blur=1.5,
    )
    img = over(img, hand, col("#0b0d14"))
    img = add(img, hand * spill, sc_col, 0.10 * screen)
    img = over(img, body, col("#020306"))
    # screen content: soft art + progress bar
    s_img = vgrad([(0, col("#1a2238")), (1, col("#0e1424"))]) * (1 - warm) + vgrad([(0, col("#3a2030")), (1, col("#1d1420"))]) * warm
    art = glow(cx - 10, cy - 70, 70) * 0.9
    s_img = add(s_img, art, col("#ffb47a") * 0.6 + col("#6a8cff") * 0.4, 0.9)
    a = math.radians(ang)
    bx0, by = cx - 70, cy + 110
    p = np.clip(progress, 0, 1)
    bar = mask_from(lambda d, s: d.line([(bx0) * s, by * s, (bx0 + 140) * s, (by + 140 * math.tan(a)) * s], fill=255, width=3 * s))
    done = mask_from(lambda d, s: d.line([(bx0) * s, by * s, (bx0 + 140 * p) * s, (by + 140 * p * math.tan(a)) * s], fill=255, width=4 * s))
    s_img = add(s_img, bar, col("#ffffff"), 0.22)
    s_img = add(s_img, done, col("#ffffff"), 0.8)
    splat_glow(s_img, bx0 + 140 * p, by + 140 * p * math.tan(a), 5, col("#ffffff"), 0.8)
    img = img * (1 - scr[..., None]) + s_img * scr[..., None] * screen + img * scr[..., None] * (1 - screen) * 0
    # thumb (tap)
    if tap is not None:
        k = tap  # 0..1 approach
        thumb = mask_from(
            lambda d, s: d.rounded_rectangle([(cx + 40 - 60 * k) * s, (cy + 140 - 60 * k) * s, (cx + 120 - 60 * k) * s, (cy + 330) * s], radius=36 * s, fill=255),
            blur=2,
        )
        img = over(img, thumb, col("#0d1018"))
    return img


# ---------------------------------------------------------------- head profile


def head(t, hp=1.0, hp_lift=0.0, warm=0.0, particles=0.0, glow_k=1.0):
    bg = vgrad([(0, col("#0b1424")), (0.5, col("#1a2a44")), (1, col("#070b13"))]) * (1 - warm) + vgrad(
        [(0, col("#2a1630")), (0.5, col("#8a4a40")), (1, col("#1a0d10"))]
    ) * warm
    lightx = 0.86 * W
    bg = add(bg, glow(lightx, 0.38 * H, 300, sy=1.4), col("#86a6d6") * (1 - warm) + col("#ffb070") * warm, 0.55 * glow_k)
    # out-of-focus window bokeh behind
    rng = np.random.default_rng(21)
    for _ in range(18):
        bx, by, r = rng.uniform(0.55, 1.0) * W, rng.uniform(0.15, 0.6) * H, rng.uniform(14, 40)
        c = col("#a9c2ea") * (1 - warm) + col("#ffc07a") * warm
        splat_disc(bg, bx + 4 * math.sin(t * 0.2), by, r, c, rng.uniform(0.04, 0.12) * glow_k, soft=0.3)
    m = mask_from(lambda d, s: profile(d, s, 0.40 * W, 0.40 * H, 175, 1, "short", headphones=hp, hp_lift=hp_lift), blur=1.0)
    img = over(bg, m, col("#04060b"))
    r = rim(m, 4, 0, 2.0) * 1.0 + rim(m, 0, 3, 2.0) * 0.4
    img = add(img, r * glow(lightx, 0.4 * H, 420), col("#b9d0f5") * (1 - warm) + col("#ffc488") * warm, 1.1 * glow_k)
    if particles > 0:
        for i in range(DUST.n):
            x = (DUST.x[i] * W + 6 * math.sin(t * 0.5 + DUST.ph[i])) % W
            y = (DUST.y[i] * H - (20 + 30 * DUST.a[i]) * t) % H
            splat_glow(img, x, y, DUST.r[i] * 1.8, col("#ffd8a0"), particles * DUST.a[i] * 0.55)
    return img


# ---------------------------------------------------------------- dream: car at night


CITY = Field(90, 31, ang=(0, 6.28), d0=(0.0, 1.0), r=(6, 30), hue=(0, 1), a=(0.25, 0.9), sp=(0.06, 0.16))


def car(t, sweep=True):
    img = vgrad([(0, col("#0a0c1a")), (0.35, col("#1b1530")), (0.6, col("#3a2235")), (1, col("#06060a"))])
    vx, vy = 0.55 * W, 0.40 * H
    img = add(img, glow(vx, vy + 30, 260, sy=0.45), col("#ff9a5a"), 0.35)
    # lights streaming outwards from the vanishing point (we are driving into the city)
    for i in range(CITY.n):
        z = (CITY.d0[i] + t * CITY.sp[i]) % 1.0
        dist = 30 + (z**2.2) * 900
        ang = CITY.ang[i]
        x = vx + math.cos(ang) * dist * 1.0
        y = vy + math.sin(ang) * dist * 0.35
        if y > 0.6 * H:
            continue
        hue = CITY.hue[i]
        c = col("#ffb35c") if hue < 0.55 else (col("#ff4a3c") if hue < 0.7 else col("#dce8ff"))
        fade = smooth(z * 6) * (1 - smooth((z - 0.85) * 6.6))
        splat_disc(img, x, y, CITY.r[i] * (0.4 + z * 1.4), c, CITY.a[i] * 0.22 * fade, soft=0.35)
    # interior silhouette: roof, A-pillars, dashboard
    inter = mask_from(
        lambda d, s: (
            d.polygon([0, 0, W * s, 0, W * s, 0.07 * H * s, 0.5 * W * s, 0.1 * H * s, 0, 0.075 * H * s], fill=255),
            d.polygon([0, 0, 0.1 * W * s, 0, 0.02 * W * s, 0.62 * H * s, 0, 0.62 * H * s], fill=255),
            d.polygon([0.93 * W * s, 0, W * s, 0, W * s, 0.62 * H * s, 0.985 * W * s, 0.62 * H * s], fill=255),
            d.polygon(catmull([(0, 0.665 * H), (0.25 * W, 0.62 * H), (0.6 * W, 0.615 * H), (W, 0.635 * H)], 10) and [(x * s, y * s) for x, y in catmull([(0, 0.665 * H), (0.25 * W, 0.62 * H), (0.6 * W, 0.615 * H), (W, 0.635 * H)], 10)] + [(W * s, H * s), (0, H * s)], fill=255),
        ),
        blur=1.2,
    )
    img = over(img, inter, col("#030409"))
    img = add(img, rim(inter, 0, -3, 2) * glow(0.5 * W, 0.62 * H, 380, sy=0.2), col("#ffb27a"), 0.5)
    img = add(img, glow(0.30 * W, 0.66 * H, 55, sy=0.35), col("#4fd0c8"), 0.22)
    # driver from behind-right: hair, neck, shoulders, one hand on the wheel
    driver = mask_from(
        lambda d, s: (
            d.polygon([(x * s, y * s) for x, y in catmull([(0.02 * W, H + 10), (0.03 * W, 0.66 * H), (0.12 * W, 0.555 * H), (0.27 * W, 0.53 * H), (0.36 * W, 0.50 * H),
                                                         (0.47 * W, 0.53 * H), (0.60 * W, 0.56 * H), (0.70 * W, 0.66 * H), (0.72 * W, H + 10)], 10)], fill=255),
            d.ellipse([0.29 * W * s, 0.375 * H * s, 0.475 * W * s, 0.525 * H * s], fill=255),
            d.ellipse([0.285 * W * s, 0.365 * H * s, 0.48 * W * s, 0.47 * H * s], fill=255),
            d.arc([0.06 * W * s, 0.585 * H * s, 0.44 * W * s, 0.80 * H * s], 190, 350, fill=255, width=int(16 * s)),
        ),
        blur=1.1,
    )
    img = over(img, driver, col("#020306"))
    img = add(img, rim(driver, -3, 0, 2) + rim(driver, 0, 3, 2) * 0.7, col("#ffb47a"), 0.8)
    if sweep:
        # passing streetlights: irregular warm sweeps across the cabin
        for k, t0 in enumerate((0.4, 1.9, 2.8, 4.6, 5.3)):
            u = (t - t0) / 1.2
            if 0 < u < 1:
                gx = lerp(1.2 * W, -0.3 * W, u)
                img = add(img, glow(gx, 0.3 * H, 260, sy=2.5) * (1 - abs(2 * u - 1)), col("#ffb466"), 0.22)
    return img


# ---------------------------------------------------------------- dream: people on a warm street


def street(t):
    img = vgrad([(0, col("#120c18")), (0.5, col("#2c1a22")), (0.8, col("#3a2320")), (1, col("#0c0809"))])
    rng = np.random.default_rng(41)
    for _ in range(55):
        bx, by, r = rng.uniform(-0.3, 1.6) * W, rng.uniform(0.15, 0.75) * H, rng.uniform(16, 55)
        x = (bx - 28 * t) % (1.9 * W) - 0.3 * W
        c = col("#ffb45e") if rng.random() < 0.75 else col("#ffe2b8")
        splat_disc(img, x, by, r, c, rng.uniform(0.05, 0.16), soft=0.3)
    img = add(img, glow(0.5 * W, 0.55 * H, 380, sy=0.7), col("#ff9550"), 0.18)
    m = mask_from(
        lambda d, s: [
            person(d, s, ((x0 - 60 * t) % (1.6 * W)) - 0.3 * W, 0.84 * H + dz, hh, 0, f, "still", headphones=False, hair=hr)
            for x0, dz, hh, f, hr in (
                (0.10 * W, 0, 0.36 * H, -1, "short"),
                (0.42 * W, 12, 0.39 * H, -1, "long"),
                (0.72 * W, -6, 0.35 * H, -1, "short"),
                (1.02 * W, 8, 0.38 * H, -1, "long"),
                (1.3 * W, 0, 0.37 * H, -1, "short"),
            )
        ],
        blur=1.4,
    )
    ground = mask_from(lambda d, s: d.rectangle([0, 0.835 * H * s, W * s, H * s], fill=255), blur=3)
    img = over(img, ground, col("#0a0607"))
    img = add(img, ground * glow(0.5 * W, 0.84 * H, 300, sy=0.15), col("#ffa160"), 0.25)
    img = over(img, m, col("#050304"))
    img = add(img, rim(m, -3, 0, 2) + rim(m, 3, 0, 2) * 0.6, col("#ffb377"), 0.8)
    return img


# ---------------------------------------------------------------- dusk sky / sea


@lru_cache(maxsize=4)
def sunset_base(variant):
    hz = 0.56 * H
    if variant == "faded":
        sky = vgrad([(0, col("#1b2030")), (0.3, col("#3a3445")), (0.5, col("#8a6a6a")), (0.56, col("#c89a7e")), (1, col("#c89a7e"))])
    else:
        sky = vgrad([(0, col("#151a3a")), (0.22, col("#3c2858")), (0.40, col("#a2466a")), (0.5, col("#f2864e")), (0.56, col("#ffcf7a")), (1, col("#ffcf7a"))])
    sea = vgrad([(0, col("#000000")), (hz / H, col("#5a3a4a")), (0.7, col("#2a2036")), (1, col("#0c0a12"))])
    if variant == "faded":
        sea = vgrad([(0, col("#000000")), (hz / H, col("#4a4048")), (0.7, col("#26242e")), (1, col("#0c0b10"))])
    img = np.where((YY < hz)[..., None], sky, sea).astype(np.float32)
    clouds = blur_fast(np.random.default_rng(9).random((H, W, 3)).astype(np.float32) * (YY < hz * 0.9)[..., None], 30)
    img += (clouds - clouds.mean()) * 0.6 * (YY < hz)[..., None]
    return img


SHIMMER = Field(260, 51, x=(-1, 1), y=(0, 1), w=(6, 40), a=(0.2, 1), ph=(0, 6.28), f=(0.5, 2.5))


def sunset(t, variant="warm", sun_k=1.0, people=None, dissolve=0.0, bloom_up=0.0):
    img = sunset_base(variant).copy()
    hz = 0.56 * H
    sx, sy = 0.5 * W, hz - 30
    sc = col("#ffe3a6") if variant != "faded" else col("#e8d0b8")
    img = add(img, glow(sx, sy, 60), sc, 1.6 * sun_k)
    img = add(img, glow(sx, sy, 210, sy=0.8), col("#ffb062") if variant != "faded" else col("#c9a090"), 0.55 * sun_k)
    img = add(img, glow(sx, hz, 520, sy=0.25), col("#ff9a55") if variant != "faded" else col("#a08080"), 0.35 * sun_k)
    # reflection shimmer column
    for i in range(SHIMMER.n):
        yy = hz + 4 + SHIMMER.y[i] ** 1.6 * (0.33 * H)
        spread = 20 + (yy - hz) * 0.55
        xx = sx + SHIMMER.x[i] * spread
        a = SHIMMER.a[i] * (0.5 + 0.5 * math.sin(t * SHIMMER.f[i] * 2 + SHIMMER.ph[i])) * (1 - (yy - hz) / (0.4 * H))
        w = SHIMMER.w[i] * (0.4 + (yy - hz) / (0.33 * H))
        x0, x1 = int(max(0, xx - w)), int(min(W, xx + w))
        y0 = int(yy)
        if x0 < x1 and 0 <= y0 < H - 2:
            seg = 1 - np.abs(np.linspace(-1, 1, x1 - x0)) ** 2
            img[y0 : y0 + 2, x0:x1] += (seg[None, :, None] * sc[None, None, :]) * a * 0.35 * sun_k
    # foreground sand
    sand = mask_from(lambda d, s: d.polygon(catmull_sand(s), fill=255), blur=2)
    img = over(img, sand, col("#0b0709") if variant != "faded" else col("#0b0a0c"))
    img = add(img, sand * glow(sx, 0.8 * H, 400, sy=0.2), col("#ff9a5e") if variant != "faded" else col("#9a8a8a"), 0.12)
    # people: list of dicts(x, h, facing, hair, phase, walk, alpha)
    if people:
        total = np.zeros((H, W), np.float32)
        for p in people:
            m = mask_from(
                lambda d, s, p=p: person(d, s, p["x"], p.get("g", 0.83 * H), p["h"], p.get("phase", 0), p["facing"], p.get("pose", "still"), headphones=False, hair=p["hair"], walk_amt=p.get("walk", 0)),
                blur=1.0,
            ) * p.get("alpha", 1.0)
            total = np.maximum(total, m)
        img = over(img, total, col("#050305"))
        img = add(img, rim(total, -3, 0, 2) + rim(total, 3, 0, 2) + rim(total, 0, 3, 2), sc, 0.6 * sun_k)
    if bloom_up > 0:
        img = img + bloom_up * 0.9 * glow(sx, sy, 600)[..., None] * col("#ffe0b0")[None, None, :]
    return img


def catmull_sand(s):
    pts = [(-20, 0.76 * H), (0.2 * W, 0.79 * H), (0.5 * W, 0.80 * H), (0.8 * W, 0.785 * H), (W + 20, 0.77 * H)]
    sm = catmull(pts, 12)
    return [(x * s, y * s) for x, y in sm] + [((W + 20) * s, (H + 20) * s), (-20 * s, (H + 20) * s)]


# ---------------------------------------------------------------- the face-off


def faceoff(t):
    img = vgrad([(0, col("#120f26")), (0.45, col("#4a2a4e")), (0.7, col("#d0704e")), (0.74, col("#ffc27a")), (1, col("#ffc27a"))])
    g = 0.75 * H
    img = add(img, glow(0.5 * W, g, 140, sx=1.0, sy=0.6), col("#fff0c8"), 1.1)
    img = add(img, glow(0.5 * W, g, 420, sx=2.5, sy=0.06), col("#ffd9a0"), 0.6)  # anamorphic streak
    img = add(img, glow(0.5 * W, g, 330), col("#ff9a55"), 0.35)
    groundm = mask_from(lambda d, s: d.rectangle([0, g * s, W * s, H * s], fill=255), blur=2)
    img = over(img, groundm, col("#0a0608"))
    img = add(img, groundm * glow(0.5 * W, g, 380, sy=0.12), col("#ff9a55"), 0.4)
    push = ease(t / 7.0)
    m = mask_from(
        lambda d, s: (
            person(d, s, 0.80 * W - 10 * push, g + 70, 0.58 * H, 0, -1, "still", headphones=False),
            person(d, s, 0.16 * W, g + 6, 0.25 * H, 0, 1, "still", headphones=False),
            person(d, s, 0.27 * W, g + 10, 0.27 * H, 0, 1, "still", headphones=False, hair="long"),
            person(d, s, 0.06 * W, g + 2, 0.24 * H, 0, 1, "still", headphones=False),
        ),
        blur=1.1,
    )
    img = over(img, m, col("#050305"))
    img = add(img, rim(m, 3, 0, 2) + rim(m, -3, 0, 2) + rim(m, 0, 3, 2), col("#ffd29a"), 0.85)
    return img


# ---------------------------------------------------------------- close profiles in sunset


def pair_close(t, gap=1.0, only_other=False, warm_bg=1.0):
    bg = vgrad([(0, col("#1c1638")), (0.35, col("#7a3a5e")), (0.55, col("#f08a52")), (0.7, col("#ffc47a")), (1, col("#3a1e22"))])
    lx = 0.5 * W
    bg = add(bg, glow(lx, 0.47 * H, 70), col("#fff0cf"), 0.9 * warm_bg)
    bg = add(bg, glow(lx, 0.5 * H, 300), col("#ffaa60"), 0.35 * warm_bg)
    rng = np.random.default_rng(61)
    for _ in range(26):
        bx, by, r = rng.uniform(0, 1) * W, rng.uniform(0.3, 0.75) * H, rng.uniform(18, 60)
        splat_disc(bg, bx + 6 * math.sin(t * 0.3 + bx), by, r, col("#ffd29a"), rng.uniform(0.04, 0.11), soft=0.35)
    if only_other:
        sway = math.sin(t * 1.1) * 1.0 + math.sin(t * 2.3) * 0.4
        m = mask_from(lambda d, s: profile(d, s, 0.36 * W, 0.42 * H, 160, 1, "long", sway=sway), blur=1.6)
        img = over(bg, m, col("#060306"))
        img = add(img, rim(m, 4, 0, 2.5) + rim(m, 0, 3, 2) * 0.5, col("#ffd7a0"), 1.2)
        # loose hair strands catching light
        for k in range(9):
            y0 = 0.36 * H + k * 9
            x0 = 0.36 * W - 0.55 * 160 - k * 3
            amp = 8 + k * 2
            for j in range(26):
                xx = x0 - j * 2.2
                yy = y0 + j * 2.0 + amp * math.sin(t * 1.4 + j * 0.25 + k)
                splat_glow(img, xx, yy, 0.9, col("#ffcf90"), 0.10)
        return img
    off = 0.20 * W * gap
    m = mask_from(
        lambda d, s: (
            profile(d, s, 0.5 * W - off - 0.13 * W, 0.52 * H, 105, 1, "short"),
            profile(d, s, 0.5 * W + off + 0.13 * W, 0.535 * H, 98, -1, "long", sway=math.sin(t)),
        ),
        blur=1.4,
    )
    img = over(bg, m, col("#060306"))
    img = add(img, rim(m, 4, 0, 2.5) + rim(m, -4, 0, 2.5), col("#ffd7a0"), 1.1)
    return img


# ---------------------------------------------------------------- rain on the window


RAIN = Field(320, 71, x=(0, 1), y=(0, 1), r=(1.5, 6.5), a=(0.4, 1.0))
RUN = Field(9, 72, x=(0.05, 0.95), y0=(-0.2, 0.6), sp=(40, 120), r=(4, 7), t0=(0, 12))


@lru_cache(maxsize=1)
def rain_bg():
    img = vgrad([(0, col("#060a14")), (0.5, col("#0c1424")), (1, col("#05070d"))])
    rng = np.random.default_rng(81)
    for _ in range(70):
        bx, by, r = rng.uniform(0, 1) * W, rng.uniform(0.2, 0.95) * H, rng.uniform(20, 70)
        c = col("#ffbf72") if rng.random() < 0.45 else (col("#9cc0ff") if rng.random() < 0.7 else col("#ff6d5a"))
        splat_disc(img, bx, by, r, c, rng.uniform(0.04, 0.13), soft=0.4, ring=0.3)
    return img


def rain(t):
    img = rain_bg().copy()
    img = add(img, glow(0.5 * W, 0.6 * H, 500), col("#2a3c5c"), 0.12)
    for i in range(RAIN.n):
        x, y, r = RAIN.x[i] * W, RAIN.y[i] * H, RAIN.r[i]
        splat_disc(img, x, y, r * 1.15, col("#05070c"), -0.45 * RAIN.a[i], soft=0.45, ring=0)
        splat_disc(img, x, y, r, col("#7f9cc8"), 0.10 * RAIN.a[i], soft=0.6, ring=0.6)
        splat_glow(img, x + r * 0.1, y + r * 0.5, r * 0.32, col("#e6f0ff"), 0.5 * RAIN.a[i])
    for i in range(RUN.n):
        tt = (t + RUN.t0[i]) % 14
        x = RUN.x[i] * W + 3 * math.sin(tt * 1.7 + i)
        y = RUN.y0[i] * H + RUN.sp[i] * tt * (0.6 + 0.4 * math.sin(tt * 0.9 + i) ** 2)
        if -50 < y < H + 50:
            for k in range(40):
                splat_glow(img, x + 1.5 * math.sin((y - k * 6) * 0.03), y - k * 6, 1.4, col("#bcd2f5"), 0.05 * (1 - k / 40))
            splat_disc(img, x, y, RUN.r[i], col("#05070c"), -0.3, soft=0.5, ring=0)
            splat_glow(img, x, y + RUN.r[i] * 0.4, RUN.r[i] * 0.45, col("#e0ecff"), 0.35)
    return img


# ---------------------------------------------------------------- dissolving into light


@lru_cache(maxsize=1)
def other_points():
    p = {"x": 0.58 * W, "h": 0.33 * H, "facing": -1, "hair": "long"}
    m = mask_from(lambda d, s: person(d, s, p["x"], 0.83 * H, p["h"], 0, -1, "still", headphones=False, hair="long"))
    ys, xs = np.nonzero(m > 0.5)
    rng = np.random.default_rng(91)
    idx = rng.choice(len(xs), 700, replace=False)
    return xs[idx].astype(np.float32), ys[idx].astype(np.float32), rng.uniform(0, 1, 700), rng.uniform(-1, 1, 700)


def farewell(t, T):
    """Two people at dusk; the other one slowly dissolves into drifting light."""
    k = smooth((t - 1.2) / (T - 3.5))
    people = [
        {"x": 0.42 * W, "h": 0.35 * H, "facing": 1, "hair": "short"},
        {"x": 0.58 * W, "h": 0.33 * H, "facing": -1, "hair": "long", "alpha": 1 - k},
    ]
    img = sunset(t, "faded", 0.85, people)
    xs, ys, delay, wob = other_points()
    for i in range(0, len(xs), 2):
        local = np.clip((k * 1.4 - delay[i] * 0.4), 0, 1)
        if local <= 0:
            continue
        x = xs[i] + local * (140 + 80 * wob[i]) + 15 * math.sin(t * 0.8 + i)
        y = ys[i] - local * (260 + 120 * delay[i])
        a = math.sin(math.pi * min(1.0, local * 1.1)) * 0.5
        splat_glow(img, x, y, 1.6 + 1.2 * local, col("#ffe0b0"), a)
    return img
