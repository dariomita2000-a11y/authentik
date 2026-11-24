"""Build German subtitles (ASS for burn-in, SRT as a sidecar) from timeline.json.

usage: python subtitles.py timeline.json out.ass out.srt cues_de.txt voice_edit.wav
"""

import json
import re
import sys

MAX_LINE = 30  # characters per line (9:16, large type)
MAX_CUE = 2 * MAX_LINE


def wrap(text):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= MAX_LINE:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) == 2 and len(lines[1]) < 10 and len(lines[0]) > 18:
        # avoid a lonely last word: rebalance
        ws = text.split()
        best = min(range(1, len(ws)), key=lambda k: abs(len(" ".join(ws[:k])) - len(" ".join(ws[k:]))))
        lines = [" ".join(ws[:best]), " ".join(ws[best:])]
    return lines


def chunks(sentence):
    """Split a long sentence into cue-sized chunks at natural breaks."""
    if len(sentence) <= MAX_CUE and len(wrap(sentence)) <= 2:
        return [sentence]
    parts = re.split(r"(?<=[,…])\s+", sentence)
    out, cur = [], ""
    for p in parts:
        cand = f"{cur} {p}".strip()
        if cur and (len(cand) > MAX_CUE or len(wrap(cand)) > 2):
            out.append(cur)
            cur = p
        else:
            cur = cand
    out.append(cur)
    final = []
    for c in out:  # still too long: split by words in half
        if len(wrap(c)) > 2:
            ws = c.split()
            k = len(ws) // 2
            final += [" ".join(ws[:k]), " ".join(ws[k:])]
        else:
            final.append(c)
    return final


def ts_ass(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def ts_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def pauses(wav):
    import subprocess

    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "silencedetect=n=-40dB:d=0.12", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return [(a + b) / 2 for a, b in zip(st, en)]


def main():
    tl = json.load(open(sys.argv[1], encoding="utf-8"))
    manual = [ln.strip() for ln in open(sys.argv[4], encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    assert len(manual) == len(tl["sentences"]), (len(manual), len(tl["sentences"]))
    gaps = pauses(sys.argv[5])
    cues = []
    for s, m in zip(tl["sentences"], manual):
        assert m.replace(" | ", " ").replace(" / ", " ") == s["text"], (m, s["text"])
        parts = [p.strip() for p in m.split("|")]
        total = sum(len(p) + 4 for p in parts)
        t = s["start"]
        for k, p in enumerate(parts):
            end = s["end"] if k == len(parts) - 1 else t + (s["end"] - s["start"]) * (len(p) + 4) / total
            if k < len(parts) - 1:
                near = [g for g in gaps if abs(g - end) < 0.6 and s["start"] < g < s["end"]]
                if near:
                    end = min(near, key=lambda g: abs(g - end))
            cues.append([t, end, p.split(" / ")])
            t = end
    for i, c in enumerate(cues):
        c[0] = max(0.0, c[0] - 0.10)
        nxt = cues[i + 1][0] - 0.10 if i + 1 < len(cues) else c[1] + 1.2
        c[1] = min(max(c[1] + 0.40, c[0] + 1.0), nxt - 0.04)

    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Inter Medium,50,&H00F4F4F4,&H00FFFFFF,&H64000000,&H8C000000,0,0,0,0,100,100,0.6,0,1,1.6,2.2,2,90,90,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(head)
        for a, b, text in cues:
            f.write(f"Dialogue: 0,{ts_ass(a)},{ts_ass(b)},Main,,0,0,0,,{{\\fad(220,260)\\blur0.6}}{'\\N'.join(text)}\n")
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        for n, (a, b, text) in enumerate(cues, 1):
            f.write(f"{n}\n{ts_srt(a)} --> {ts_srt(b)}\n" + "\n".join(text) + "\n\n")
    for a, b, text in cues:
        print(f"{a:7.2f} {b:7.2f} | " + " / ".join(text))


if __name__ == "__main__":
    main()
