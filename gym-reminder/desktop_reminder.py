#!/usr/bin/env python3
"""Desktop-Variante des Gym Reminders.

Browser können Benachrichtigungen nur zuverlässig schicken, solange die Seite
offen ist. Wer die Erinnerungen auch bei geschlossenem Browser will, lässt
dieses Skript im Hintergrund laufen — es nutzt dieselben Sprüche wie die
Web-App (gelesen aus ``quotes.js``, damit es nur eine Quelle gibt).

Beispiele:

    python3 desktop_reminder.py                       # 18:00 Uhr, Spruch alle 4 h
    python3 desktop_reminder.py --time 07:30 --every 2
    python3 desktop_reminder.py --days mo,di,mi,do,fr
    python3 desktop_reminder.py --test                # einmal senden und beenden
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

QUOTES_FILE = Path(__file__).with_name("quotes.js")
QUIET_START_HOUR = 22
QUIET_END_HOUR = 7
DAY_NAMES = ["mo", "di", "mi", "do", "fr", "sa", "so"]


def load_quotes() -> list[str]:
    """Liest die ``text``-Felder aus dem Array in ``quotes.js``.

    Die Begründungen (``why``) bleiben außen vor — eine Benachrichtigung soll
    kurz sein.
    """
    source = QUOTES_FILE.read_text(encoding="utf-8")
    array = re.search(r"GYM_QUOTES\s*=\s*\[(.*?)\n    \];", source, re.DOTALL)
    if not array:
        raise SystemExit(f"Keine Sprüche in {QUOTES_FILE} gefunden.")
    quotes = re.findall(r'text:\s*"((?:[^"\\]|\\.)*)"', array.group(1))
    if not quotes:
        raise SystemExit(f"Keine Sprüche in {QUOTES_FILE} gefunden.")
    return [quote.replace('\\"', '"') for quote in quotes]


def notify(title: str, message: str) -> None:
    """Zeigt eine Desktop-Benachrichtigung auf macOS, Linux oder Windows."""
    if sys.platform == "darwin":
        # AppleScript-Strings sind wie JSON-Strings gequotet.
        script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
        subprocess.run(["osascript", "-e", script], check=False)
    elif sys.platform.startswith("win"):

        def ps_quote(text: str) -> str:
            return "'" + text.replace("'", "''") + "'"

        powershell = (
            "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') > $null;"
            " $balloon = New-Object System.Windows.Forms.NotifyIcon;"
            " $balloon.Icon = [System.Drawing.SystemIcons]::Information;"
            f" $balloon.BalloonTipTitle = {ps_quote(title)};"
            f" $balloon.BalloonTipText = {ps_quote(message)};"
            " $balloon.Visible = $true; $balloon.ShowBalloonTip(10000); Start-Sleep -Seconds 10"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", powershell], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)
    else:
        print(f"[{datetime.now():%H:%M}] {title}: {message}", flush=True)


def parse_days(value: str) -> set[int]:
    """``"mo,di,fr"`` -> Menge von ``date.weekday()``-Werten (Montag = 0)."""
    days = set()
    for part in value.split(","):
        name = part.strip().lower()[:2]
        if name not in DAY_NAMES:
            raise argparse.ArgumentTypeError(f"Unbekannter Tag: {part!r}")
        days.add(DAY_NAMES.index(name))
    if not days:
        raise argparse.ArgumentTypeError("Mindestens ein Trainingstag nötig.")
    return days


def parse_time(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if not match:
        raise argparse.ArgumentTypeError("Uhrzeit im Format HH:MM angeben, z. B. 18:00.")
    hours, minutes = int(match.group(1)), int(match.group(2))
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        raise argparse.ArgumentTypeError("Ungültige Uhrzeit.")
    return hours, minutes


def is_quiet(moment: datetime, respect_quiet_hours: bool) -> bool:
    return respect_quiet_hours and (moment.hour >= QUIET_START_HOUR or moment.hour < QUIET_END_HOUR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tägliche Gym-Erinnerung mit Motivationssprüchen.")
    parser.add_argument(
        "--time", default="18:00", type=parse_time, help="Uhrzeit der Erinnerung (HH:MM)."
    )
    parser.add_argument(
        "--days",
        default="mo,di,mi,do,fr",
        type=parse_days,
        help="Trainingstage, z. B. mo,mi,fr (Standard: mo,di,mi,do,fr).",
    )
    parser.add_argument(
        "--every",
        default=4.0,
        type=float,
        help="Abstand der Motivationssprüche in Stunden; 0 schaltet sie aus (Standard: 4).",
    )
    parser.add_argument(
        "--no-quiet-hours", action="store_true", help="Auch nachts benachrichtigen."
    )
    parser.add_argument(
        "--test", action="store_true", help="Eine Benachrichtigung senden und beenden."
    )
    args = parser.parse_args()

    quotes = load_quotes()
    respect_quiet_hours = not args.no_quiet_hours

    if args.test:
        notify("Zeit fürs Gym 🏋️", random.choice(quotes))
        return 0

    hours, minutes = args.time
    next_quote_at = datetime.now() + timedelta(hours=args.every) if args.every > 0 else None
    last_reminder_day = None

    print(
        f"Gym Reminder läuft: {hours:02d}:{minutes:02d} Uhr an "
        f"{','.join(DAY_NAMES[day] for day in sorted(args.days))}"
        + (f", Sprüche alle {args.every:g} h" if args.every > 0 else ", ohne Sprüche")
        + ". Beenden mit Strg+C.",
        flush=True,
    )

    try:
        while True:
            now = datetime.now()
            due = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            if (
                now.weekday() in args.days
                and last_reminder_day != now.date()
                and due <= now < due + timedelta(hours=4)
            ):
                notify("Zeit fürs Gym 🏋️", random.choice(quotes))
                last_reminder_day = now.date()

            if next_quote_at and now >= next_quote_at:
                if not is_quiet(now, respect_quiet_hours):
                    notify("Motivation für dich 💪", random.choice(quotes))
                next_quote_at = now + timedelta(hours=args.every)

            time.sleep(30)
    except KeyboardInterrupt:
        print("\nBis morgen.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
