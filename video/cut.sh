#!/bin/sh
# Cut each recording (out/rec/*.webm, from record.mjs) to its slot in front-door.tsx: drop the page load, then speed it
# up so it fills the slot exactly. Output: media/<shot>.mp4 (H.264, 30 fps, no audio).
set -e
cd "$(dirname "$0")"
mkdir -p media
cut() { # shot source trim_in_s slot_s
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "out/rec/$2.webm")
  speed=$(echo "($dur - $3) / $4" | bc -l)
  ffmpeg -loglevel error -y -ss "$3" -i "out/rec/$2.webm" -an -vf "setpts=PTS/$speed,fps=30" -t "$4" \
    -c:v libx264 -pix_fmt yuv420p -crf 16 "media/$1.mp4"
  printf '%s %.2fx\n' "$1" "$speed"
}
cut hook e-injection 1.0 5
cut voice-fi a-voice-fi 1.0 12
cut held b-held 1.0 10
cut approve c-approve-phone 1.0 9
cut sugar d-sugar 1.0 6
cut menu f-menu 1.0 11
cut urgent-voice g-urgent-voice 1.0 13
cut history h-history 0.8 4
cut rules i-rules 0.8 4
