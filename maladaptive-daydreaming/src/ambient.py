"""Procedural ambient score: sparse soft piano + dark drone + air. No beats, no rhythm.

usage: python ambient.py cues.json out.wav
cues.json: {"duration": s, "fantasy_start": s, "fantasy_peak": s, "song_end": s,
            "headphones_off": s, "outro_start": s}
"""

import json
import sys

import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def env_curve(t, points):
    """Piecewise-linear automation. points: [(time, value), ...]"""
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def fft_lowpass(x, cutoff, order=2):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X *= 1 / np.sqrt(1 + (f / cutoff) ** (2 * order))
    return np.fft.irfft(X, n)


def fft_bandpass(x, lo, hi):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X *= (1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** 4)) * (1 / np.sqrt(1 + (f / hi) ** 4))
    return np.fft.irfft(X, n)


def piano_note(freq, dur, vel=0.5):
    """Soft, felt-like piano tone: inharmonic partials, fast attack, two-stage decay."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    B = 0.00012  # inharmonicity
    for k in range(1, 9):
        fk = freq * k * np.sqrt(1 + B * k * k)
        if fk > 9000:
            break
        amp = (1.0 / k**1.6) * (vel ** (0.6 + 0.25 * k))  # softer -> fewer highs (felt piano)
        decay = 1.2 + 4.0 / k  # higher partials die faster
        e = 0.7 * np.exp(-t / (decay * 0.35)) + 0.3 * np.exp(-t / (decay * 2.2))
        detune = 1 + rng.normal(0, 0.0004)
        out += amp * e * np.sin(2 * np.pi * fk * detune * t + rng.uniform(0, 6.28))
    attack = np.minimum(1, t / 0.012)
    hammer = np.exp(-t / 0.01) * rng.normal(0, 1, n) * 0.02 * vel
    out = out * attack + fft_lowpass(hammer, 1800)
    release = np.minimum(1, (dur - t) / 0.8)
    return out * np.clip(release, 0, 1)


def reverb(x, seconds=5.5, wet=0.55, predelay=0.03):
    """Convolution reverb with a synthetic stereo hall IR (FFT)."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    irs = []
    for ch in range(2):
        noise = rng.normal(0, 1, n)
        noise = fft_lowpass(noise, 5200)
        ir = noise * np.exp(-t * 6.9 / seconds)  # -60 dB at `seconds`
        ir *= np.minimum(1, t / 0.02)
        ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
        irs.append(ir / np.sqrt(np.sum(ir**2)))
    L = len(x) + len(irs[0])
    nfft = 1 << (L - 1).bit_length()
    X = np.fft.rfft(x, nfft)
    wetL = np.fft.irfft(X * np.fft.rfft(irs[0], nfft), nfft)[: len(x)]
    wetR = np.fft.irfft(X * np.fft.rfft(irs[1], nfft), nfft)[: len(x)]
    dry = x * (1 - wet)
    return np.stack([dry + wet * wetL, dry + wet * wetR], axis=1)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def main():
    cues = json.load(open(sys.argv[1]))
    D = cues["duration"]
    N = int(D * SR)
    t = np.arange(N) / SR
    fs, fp, se, ho, oo = (
        cues["fantasy_start"],
        cues["fantasy_peak"],
        cues["song_end"],
        cues["headphones_off"],
        cues["outro_start"],
    )

    # ---------- dark drone (D minor world) ----------
    drone = np.zeros(N)
    for m, a in [(38, 0.5), (45, 0.32), (50, 0.22), (53, 0.12), (57, 0.08)]:
        for d in (-0.07, 0.0, 0.06):
            f = midi(m) * (1 + d / 100)
            lfo = 1 + 0.003 * np.sin(2 * np.pi * rng.uniform(0.03, 0.08) * t + rng.uniform(0, 6))
            drone += a * np.sin(2 * np.pi * f * t * lfo + rng.uniform(0, 6.28))
    # slow breathing amplitude
    drone *= 0.75 + 0.25 * np.sin(2 * np.pi * t / 17.0) ** 2
    # fantasy: warmer, fuller (add fifth/ninth shimmer)
    shimmer = np.zeros(N)
    for m in (62, 69, 76, 81):
        f = midi(m)
        shimmer += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (
            0.5 + 0.5 * np.sin(2 * np.pi * t / rng.uniform(9, 15) + rng.uniform(0, 6))
        )
    shimmer = fft_lowpass(shimmer, 2500) * 0.05

    drone_gain = env_curve(
        t,
        [
            (0, 0), (4, 0.55), (fs, 0.6), (fp, 0.95), (se - 1.0, 0.85),
            (se + 0.4, 0.05), (ho + 2.5, 0.0), (oo - 2, 0.0), (oo + 6, 0.45), (D - 5, 0.4), (D, 0),
        ],
    )
    shimmer_gain = env_curve(t, [(0, 0), (fs, 0), (fp, 1.0), (se - 1, 0.9), (se + 0.3, 0), (D, 0)])

    # ---------- air / room tone ----------
    air = fft_bandpass(rng.normal(0, 1, N), 150, 1200) * 0.06
    air_gain = env_curve(t, [(0, 0), (3, 0.6), (se, 0.5), (se + 0.5, 1.0), (oo, 0.9), (D - 3, 0.5), (D, 0)])

    # ---------- sparse piano ----------
    piano = np.zeros(N + SR * 8)
    # D minor / Bb maj7 / F / A-minor colors; long irregular gaps, never a beat grid
    phrases = [
        [74, 69, 65], [72, 67], [70, 74, 77], [69, 65], [74, 72, 69], [65, 69, 72, 76], [70, 65], [69],
    ]
    bass = [50, 46, 53, 45]
    time_cursor = 3.0
    pi = 0
    while time_cursor < D - 4:
        in_fantasy = fs < time_cursor < se
        in_void = se - 0.5 < time_cursor < oo
        if in_void:
            time_cursor = oo + 1.5
            continue
        phrase = phrases[pi % len(phrases)]
        if pi % 2 == 0:
            b = bass[(pi // 2) % len(bass)]
            note = piano_note(midi(b), 7.0, vel=0.35)
            s = int(time_cursor * SR)
            piano[s : s + len(note)] += note * 0.6
        for j, m in enumerate(phrase):
            onset = time_cursor + j * rng.uniform(0.9, 1.7)
            vel = rng.uniform(0.28, 0.42) * (1.1 if in_fantasy else 1.0)
            note = piano_note(midi(m + (12 if in_fantasy and j == len(phrase) - 1 else 0)), 6.5, vel)
            s = int(onset * SR)
            piano[s : s + len(note)] += note
        gap = rng.uniform(5.5, 8.5) if not in_fantasy else rng.uniform(4.0, 6.0)
        time_cursor += gap
        pi += 1
    # final lone note on the last words
    for m, off in [(62, 0.0), (69, 2.2), (65, 4.6)]:
        note = piano_note(midi(m), 8.0, 0.3)
        s = int((cues.get("final_note", D - 10) + off) * SR)
        piano[s : s + len(note)] += note
    piano = piano[:N]
    piano_gain = env_curve(t, [(0, 1), (se, 1), (se + 0.2, 0), (oo, 0), (oo + 0.5, 1), (D, 1)])

    mono_tonal = drone * drone_gain * 0.05 + shimmer * shimmer_gain + piano * piano_gain * 0.09
    mono_tonal = fft_lowpass(mono_tonal, 6000)
    st = reverb(mono_tonal, seconds=6.0, wet=0.6)
    airL = air * air_gain
    airR = np.roll(air, 4801) * air_gain
    st[:, 0] += airL
    st[:, 1] += airR

    # normalise score so it sits far below the voice (peak ~ -18 dBFS)
    st /= np.max(np.abs(st)) + 1e-9
    st *= 10 ** (-18 / 20)
    fade = np.minimum(1, (D - t) / 3.0)[:, None]
    st *= np.clip(fade, 0, 1)

    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    import wave

    with wave.open(sys.argv[2], "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main()
