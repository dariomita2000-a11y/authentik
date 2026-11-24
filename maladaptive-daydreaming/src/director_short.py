"""Shot list + renderer. Pipes raw frames to ffmpeg.

usage: python director_short.py timeline.json out.mp4 [--stills t1,t2,...] [--fps 30] [--range a,b]
"""

import json
import math
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

import scenes as S
from gfx import H, W, blur_fast, camera, ease, finish, lerp, smooth

TL = json.load(open(sys.argv[1], encoding="utf-8"))
SENT = TL["sentences"]
CUE = TL["cues"]
DUR = CUE["duration"]


def st(prefix):
    return next(s["start"] for s in SENT if s["text"].startswith(prefix))


def en(prefix):
    return next(s["end"] for s in SENT if s["text"].startswith(prefix))


# --------------------------------------------------------------------------- shots
# (start, render(t_local, T), xfade_in_seconds, cam(z0, z1, cx, cy), grade dict)


def shot(start, fn, xf=1.0, cam=(1.0, 1.06, 0.5, 0.5), **grade):
    return {"start": start, "fn": fn, "xf": xf, "cam": cam, "grade": grade}


T_SETZT = st("Setzt deine Kopfhörer")
T_LAUF = st("Und läufst durch")
T_HIN = st("Hin… und her")
T_GEDANKEN = st("Aber in Gedanken")
T_LEBEN = st("Du lebst ein anderes")
T_MENSCHEN = st("Menschen sehen dich")
T_GESPR = st("Du führst Gespräche")
T_GESPR_END = en("Du führst Gespräche")
T_ECHTER = st("Für einen Moment")
T_ENDE = st("Dann endet das Lied")
T_ZIMMER = st("Und du stehst wieder")
T_NENNT = st("Man nennt es")
T_TAG = st("Tagträume")
T_LETZT = st("Und manchmal vermisst")
T_LETZT_END = en("Und manchmal vermisst")

SHOTS = [
    # --- reality: music on, headphones, pacing
    shot(0.0, lambda t, T: S.phone(t, progress=0.02 + t * 0.004, screen=smooth((t - 0.2) / 1.0)), xf=0, cam=(1.0, 1.06, 0.5, 0.6), bloom=0.3),
    shot(T_SETZT - 0.25, lambda t, T: S.head(t, hp=1.0, hp_lift=max(0.0, 90 * (1 - ease((t - 0.15) / 1.1)))), xf=0.6, cam=(1.04, 1.09, 0.45, 0.42), bloom=0.35),
    shot(T_LAUF - 0.2, lambda t, T: S.room(t + 1.5), xf=0.8, cam=(1.0, 1.05, 0.5, 0.55), bloom=0.3),
    shot(T_HIN - 0.1, lambda t, T: S.room(t * 0.8 + 3.0, fig_h=0.74, ground=0.975, xr=(0.12, 0.88), walk_speed=0.85, dusty=0.6), xf=0.6, cam=(1.0, 1.04, 0.5, 0.8), bloom=0.3),
    shot(T_GEDANKEN - 0.1, lambda t, T: S.room(t + 6.0, ghost=smooth(t / 1.2) * 0.9, fig_alpha=1 - 0.4 * smooth(t / 1.6)), xf=0.7, cam=(1.12, 1.18, 0.5, 0.5), bloom=0.3),
    shot(T_GEDANKEN + 1.5, lambda t, T: S.head(t + 1.0, hp=1.0, warm=smooth(t / 1.6), particles=smooth((t - 0.3) / 1.5), glow_k=1 + smooth(t / 1.6) * 0.6), xf=0.9, cam=(1.05, 1.14, 0.45, 0.42), bloom=0.45, warm=0.3),
    # --- the dream
    shot(T_LEBEN - 0.3, lambda t, T: S.car(t + 1.0), xf=1.2, cam=(1.06, 1.0, 0.5, 0.45), bloom=0.55, warm=0.5, dream=1),
    shot(T_MENSCHEN - 0.2, lambda t, T: S.street(t), xf=0.8, cam=(1.04, 1.09, 0.5, 0.6), bloom=0.55, warm=0.5, dream=1),
    shot(
        T_GESPR - 0.2,
        lambda t, T: S.sunset(
            t,
            people=[
                {"x": lerp(0.24 * W, 0.38 * W, t / T), "h": 0.31 * H, "facing": 1, "hair": "short", "pose": "walk", "phase": t * 3.0, "walk": 0.8},
                {"x": lerp(0.80 * W, 0.68 * W, t / T), "h": 0.29 * H, "facing": -1, "hair": "long", "pose": "walk", "phase": t * 2.6 + 1, "walk": 0.6},
            ],
        ),
        xf=0.9, cam=(1.0, 1.07, 0.5, 0.6), bloom=0.6, warm=0.7, dream=1,
    ),
    shot(T_GESPR + 3.2, lambda t, T: S.pair_close(t, gap=lerp(0.9, 0.5, ease(t / T))), xf=0.9, cam=(1.0, 1.07, 0.5, 0.48), bloom=0.65, warm=0.7, dream=1),
    shot(
        T_ECHTER - 0.2,
        lambda t, T: S.sunset(
            t,
            people=[
                {"x": 0.455 * W, "h": 0.36 * H, "facing": 1, "hair": "short"},
                {"x": 0.545 * W, "h": 0.34 * H, "facing": -1, "hair": "long"},
            ],
            bloom_up=smooth((t - (T - 2.6)) / 2.2) * 0.5,
        ),
        xf=0.9, cam=(1.0, 1.12, 0.5, 0.6), bloom=0.7, warm=0.8, dream=1,
    ),
    # --- the song ends
    shot(T_ENDE - 0.35, lambda t, T: S.phone(t, progress=0.985 + t * 0.006, screen=1 - smooth((t - 1.0) / 0.8) * 0.85), xf=0.3, cam=(1.12, 1.15, 0.5, 0.6), bloom=0.25),
    shot(T_ENDE + 1.1, lambda t, T: S.head(t, hp=1.0 - smooth((t - 0.9) / 0.5), hp_lift=90 * ease((t - 0.1) / 1.0)), xf=0.5, cam=(1.06, 1.09, 0.45, 0.42), bloom=0.3),
    shot(T_ZIMMER + 0.2, lambda t, T: S.room(t, figure="still", still_x=0.54, dusty=1.2, light=0.92, hp=False), xf=1.0, cam=(1.0, 1.08, 0.5, 0.56), bloom=0.25, grain=0.04),
    # --- what it is
    shot(T_NENNT - 0.4, lambda t, T: S.rain(t), xf=1.2, cam=(1.0, 1.06, 0.5, 0.5), bloom=0.35),
    shot(T_TAG - 0.2, lambda t, T: S.room(t, figure="sit", dusty=0.8, light=0.85, hp=False), xf=1.1, cam=(1.0, 1.07, 0.42, 0.62), bloom=0.25),
    # --- longing
    shot(T_LETZT - 0.4, lambda t, T: S.farewell(t + 0.6, T + 0.6), xf=1.3, cam=(1.0, 1.1, 0.5, 0.62), bloom=0.45, warm=0.2, dream=0.5, sat=0.75),
    shot(T_LETZT_END - 3.4, lambda t, T: S.room(t, figure="still", still_x=0.5, facing_still=1, dusty=1.0, hp=False, light=max(0.0, 1 - smooth((t - 2.0) / 3.0))), xf=1.2, cam=(1.0, 1.1, 0.5, 0.48), bloom=0.25),
]
for i, s in enumerate(SHOTS):
    s["end"] = SHOTS[i + 1]["start"] + SHOTS[i + 1]["xf"] if i + 1 < len(SHOTS) else DUR
    s["T"] = s["end"] - s["start"]


def render_shot(s, t):
    lt = t - s["start"]
    if s["fn"] == "double":
        a = S.room(lt + 4.0)
        b = S.sunset(lt + 20, people=[{"x": 0.45 * W, "h": 0.32 * H, "facing": 1, "hair": "short"}, {"x": 0.57 * W, "h": 0.30 * H, "facing": -1, "hair": "long"}])
        k = 0.35 + 0.3 * smooth(lt / s["T"])
        img = 1 - (1 - np.clip(a * 1.2, 0, 1)) * (1 - np.clip(b * k, 0, 1))  # screen blend
    else:
        img = s["fn"](lt, s["T"])
    z0, z1, cx, cy = s["cam"]
    u = ease(lt / max(s["T"], 0.01))
    return camera(img, lerp(z0, z1, u), cx, cy)


GRADE_DEFAULT = {"bloom": 0.3, "warm": 0.0, "grain": 0.035, "dream": 0.0, "sat": 1.0}


def grade_of(s):
    g = dict(GRADE_DEFAULT)
    g.update(s["grade"])
    return g


def frame(i, fps):
    t = i / fps
    act = [s for s in SHOTS if s["start"] <= t < s["end"]]
    cur = act[-1]
    img = render_shot(cur, t)
    g = grade_of(cur)
    if len(act) > 1 and cur["xf"] > 0:
        prev = act[-2]
        k = ease((t - cur["start"]) / cur["xf"])
        pimg = render_shot(prev, t)
        dream = max(g["dream"], grade_of(prev)["dream"])
        mix = pimg * (1 - k) + img * k
        if dream > 0:
            # dreamy dissolve: soft bloom peak in the middle of the transition
            mid = math.sin(math.pi * k)
            mix = mix * (1 - 0.35 * mid * dream) + blur_fast(mix, 18) * 0.55 * mid * dream
        img = mix
        pg = grade_of(prev)
        g = {key: lerp(pg[key], g[key], k) for key in g}
    # dream softness (subtle halation and chroma bleed)
    if g["dream"] > 0:
        img = img * (1 - 0.18 * g["dream"]) + blur_fast(img, 10) * 0.22 * g["dream"]
    if g["sat"] != 1.0:
        lum = img.mean(axis=2, keepdims=True)
        img = lum + (img - lum) * g["sat"]
    # global fade from black at the very start / to black at the very end
    fade_in = smooth(t / 1.2)
    img = img * fade_in
    out = finish(img, i, grain=g["grain"], bloom=g["bloom"], warm=g["warm"])
    return (out * 255 + 0.5).astype(np.uint8)


def _job(args):
    i, fps = args
    return frame(i, fps).tobytes()


def main():
    args = sys.argv[3:]
    fps = 30
    if "--fps" in args:
        fps = int(args[args.index("--fps") + 1])
    if "--stills" in args:
        ts = [float(x) for x in args[args.index("--stills") + 1].split(",")]
        for t in ts:
            Image.fromarray(frame(int(t * fps), fps)).save(f"{sys.argv[2]}_{t:06.2f}.png")
        return
    a, b = 0, int(DUR * fps)
    if "--range" in args:
        r = args[args.index("--range") + 1].split(",")
        a, b = int(float(r[0]) * fps), int(float(r[1]) * fps)
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", sys.argv[2]],
        stdin=subprocess.PIPE,
    )
    import multiprocessing as mp

    with mp.get_context("fork").Pool(4) as pool:
        for n, buf in enumerate(pool.imap(_job, [(i, fps) for i in range(a, b)], chunksize=4)):
            ff.stdin.write(buf)
            if n % 300 == 0:
                print(f"frame {a + n}/{b}", flush=True)
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
