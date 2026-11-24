"""Insert breathing room into the narration and produce the master timeline.

usage: python timeline.py voice.mp3 align_raw.json out_voice.wav timeline.json
"""

import json
import subprocess
import sys

import numpy as np

SR = 48000
LEAD_IN = 1.5  # room tone before the first word
TAIL = 3.5  # black/silence after the last word

# extra silence inserted AFTER the sentence that starts with this text
GAPS = {
    "In deinem Kopf beginnt": 1.0,
    "Für einen Moment": 1.2,
    "Doch irgendwann endet": 0.6,
    "Du nimmst deine Kopfhörer": 2.4,
    "Allein.": 0.8,
    "Zurück in diese Welt": 1.0,
    "Aber nicht jeder": 0.8,
    "Sondern das, wonach": 1.0,
    "Manchmal vermisst du auch": 1.0,
}


def load(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.float32).copy()


def main():
    voice = load(sys.argv[1])
    sents = json.load(open(sys.argv[2], encoding="utf-8"))
    pieces = [np.zeros(int(LEAD_IN * SR), np.float32)]
    cursor = 0  # sample position in source
    shift = LEAD_IN
    out_sents = []
    for s in sents:
        gap = next((g for k, g in GAPS.items() if s["text"].startswith(k)), 0.0)
        out_sents.append({"text": s["text"], "start": round(s["start"] + shift, 3), "end": round(s["end"] + shift, 3)})
        if gap:
            # cut point: just after the sentence ends (inside the following silence)
            cut = int((s["end"] + 0.12) * SR)
            pieces.append(voice[cursor:cut])
            # crossfade-free: the cut sits in near-silence; insert pure silence
            pieces.append(np.zeros(int(gap * SR), np.float32))
            cursor = cut
            shift += gap
    pieces.append(voice[cursor:])
    pieces.append(np.zeros(int(TAIL * SR), np.float32))
    out = np.concatenate(pieces)
    total = len(out) / SR
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", sys.argv[3]],
        input=out.tobytes(),
        check=True,
    )

    def find(prefix, key="start"):
        return next(s[key] for s in out_sents if s["text"].startswith(prefix))

    cues = {
        "duration": round(total, 3),
        "fantasy_start": find("In deinem Kopf beginnt"),
        "fantasy_peak": find("Und während du durch dein Zimmer"),
        "song_end": find("Doch irgendwann endet"),
        "headphones_off": find("Du nimmst deine Kopfhörer"),
        "outro_start": find("Vielleicht startest du"),
        "final_note": find("Ein Leben…"),
    }
    json.dump({"cues": cues, "sentences": out_sents}, open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(cues, indent=1))


if __name__ == "__main__":
    main()
