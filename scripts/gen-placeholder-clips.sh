#!/usr/bin/env bash
# Generate short synthetic MP4s for the placeholder adventure (no third-party IP).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/examples/placeholder/clips"
mkdir -p "$OUT"

gen() {
  local name="$1" color="$2" title="$3" seconds="$4"
  local file="$OUT/$name.mp4"
  echo "→ $file ($seconds s)"
  ffmpeg -y -hide_banner -loglevel error \
    -f lavfi -i "color=c=${color}:s=960x540:d=${seconds}" \
    -vf "drawtext=text='${title}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2:font=Sans" \
    -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
    "$file"
}

gen intro        0x163a45 "INTRO — door creaks"     4
gen hallway      0x2a2438 "HALLWAY — footsteps"     4.2
gen exit         0x1e3d2f "EXIT — you escape"       3.5
gen death_splash 0x4a1515 "DEATH — SPLASH"          2.2
gen death_stomp  0x3a1020 "DEATH — STOMP"           2.2

echo "Done. Clips in $OUT"
