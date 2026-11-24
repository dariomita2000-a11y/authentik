"""Align script sentences to the narration via pause detection + monotonic DP.

usage: python align.py voice.mp3 sprechertext.txt out.json
Writes [{"text": sentence, "start": s, "end": s}, ...]
"""

import json
import math
import re
import subprocess
import sys


def speech_segments(path, noise="-42dB", d=0.28):
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=n={noise}:d={d}", "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stderr
    dur = float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", log).groups()[2]) + 60 * float(
        re.search(r"Duration: (\d+):(\d+)", log).groups()[1]
    )
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    segs, p = [], 0.0
    for s, e in zip(starts, ends):
        if s - p > 0.05:
            segs.append([p, s])
        p = e
    if dur - p > 0.15 and len(ends) == len(starts):
        segs.append([p, dur])
    return segs


def sentences(script):
    text = re.sub(r"\[[^\]]+\]", " ", script)
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def weight(s):
    return len(re.sub(r"[^\wäöüÄÖÜß]", "", s)) + 4


def main():
    segs = speech_segments(sys.argv[1])
    sents = sentences(open(sys.argv[2], encoding="utf-8").read())
    total_speech = sum(e - s for s, e in segs)
    total_w = sum(weight(s) for s in sents)
    k = total_speech / total_w
    S, U = len(segs), len(sents)
    INF = float("inf")
    # dp[i][j]: best cost aligning first i sentences to first j segments
    dp = [[INF] * (S + 1) for _ in range(U + 1)]
    bp = [[None] * (S + 1) for _ in range(U + 1)]
    dp[0][0] = 0.0
    for i in range(U + 1):
        for j in range(S + 1):
            if dp[i][j] == INF:
                continue
            for a in range(1, 4):  # sentences in group
                if i + a > U:
                    break
                w = sum(weight(x) for x in sents[i : i + a])
                for b in range(1, 6):  # segments in group
                    if j + b > S:
                        break
                    dur = sum(e - s for s, e in segs[j : j + b])
                    c = math.log(dur / (k * w)) ** 2 + 0.15 * (a - 1) + 0.03 * (b - 1)
                    if dp[i][j] + c < dp[i + a][j + b]:
                        dp[i + a][j + b] = dp[i][j] + c
                        bp[i + a][j + b] = (i, j)
    i, j = U, S
    groups = []
    while (i, j) != (0, 0):
        pi, pj = bp[i][j]
        groups.append((pi, i, pj, j))
        i, j = pi, pj
    groups.reverse()
    out = []
    for si, ei, sj, ej in groups:
        gsegs = segs[sj:ej]
        if ei - si == 1:
            out.append({"text": sents[si], "start": gsegs[0][0], "end": gsegs[-1][1]})
            continue
        # several sentences in one group: split speech time by weight
        ws = [weight(x) for x in sents[si:ei]]
        speech = sum(e - s for s, e in gsegs)
        cum, targets = 0, []
        for w in ws:
            cum += w
            targets.append(cum / sum(ws) * speech)

        def at(tt):
            acc = 0
            for s, e in gsegs:
                if acc + (e - s) >= tt - 1e-9:
                    return s + (tt - acc)
                acc += e - s
            return gsegs[-1][1]

        prev = gsegs[0][0]
        for n, tt in enumerate(targets):
            end = at(tt)
            out.append({"text": sents[si + n], "start": prev, "end": end})
            prev = end
    json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for o in out:
        print(f"{o['start']:7.2f} {o['end']:7.2f}  {o['text']}")


if __name__ == "__main__":
    main()
