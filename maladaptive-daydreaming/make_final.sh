#!/usr/bin/env bash
# Final master: rendered picture + burned-in German subtitles + mixed audio.
set -euo pipefail
cd "$(dirname "$0")"

ffmpeg -v error -y \
  -i build/video_nosound.mp4 -i audio/mix_final.wav \
  -vf "ass=build/untertitel.ass" \
  -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 19 -profile:v high -level 4.2 -pix_fmt yuv420p \
  -x264-params "aq-mode=3:deblock=-1,-1" -r 30 \
  -c:a aac -b:a 256k -ar 48000 \
  -movflags +faststart -shortest \
  build/Tagtraum_Maladaptive_Daydreaming_9x16.mp4

# Clean version without burned-in subtitles (subtitles as .srt for the platform's own captions)
ffmpeg -v error -y \
  -i build/video_nosound.mp4 -i audio/mix_final.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -ar 48000 -movflags +faststart -shortest \
  build/Tagtraum_ohne_Untertitel_9x16.mp4

ls -la build/*.mp4
