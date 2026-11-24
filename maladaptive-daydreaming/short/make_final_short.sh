#!/usr/bin/env bash
# Final short master (<= 59 s): picture + burned-in German subtitles + mixed audio.
set -euo pipefail
cd "$(dirname "$0")"

OUT=build/Tagtraum_Shorts_9x16.mp4
ffmpeg -v error -y \
  -i build/video_nosound.mp4 -i mix_final.wav \
  -vf "ass=untertitel_short.ass" \
  -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 21 -maxrate 12M -bufsize 24M -profile:v high -level 4.2 -pix_fmt yuv420p \
  -x264-params "aq-mode=3:deblock=-1,-1" -r 30 \
  -c:a aac -b:a 256k -ar 48000 \
  -movflags +faststart -shortest \
  "$OUT"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
echo "duration: ${DUR}s"
python3 -c "import sys; d=float('$DUR'); sys.exit(0 if d < 59.0 else 1)" || { echo "ERROR: video is ${DUR}s (limit 59s)"; exit 1; }
ls -la "$OUT"
