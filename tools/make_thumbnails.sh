#!/usr/bin/env bash
# Rebuild the 16:9 project thumbnails used in the profile README.
#
# Sources are the media files already published in each project repository,
# so every thumbnail shows real project output. Requires: curl, ffmpeg.
#
#   bash tools/make_thumbnails.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/assets/projects"
RAW="https://raw.githubusercontent.com/SahilMalwanker"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

# Shared GIF encoder: one 192-colour palette per clip, ordered dithering
# (stable between frames, so it compresses well) and rectangle-diff updates.
gif() { # gif <repo> <path-in-repo> <filter> <fps> <output-name> [start-s] [length-s] [colours]
  local src="$TMP/$(basename "$2")"
  local window=()
  [[ -n "${6:-}" ]] && window+=(-ss "$6")
  [[ -n "${7:-}" ]] && window+=(-t "$7")
  curl -fsSL "$RAW/$1/main/$2" -o "$src"
  ffmpeg -v error -y ${window[@]+"${window[@]}"} -i "$src" -vf \
    "$3,fps=$4,split[a][b];[a]palettegen=max_colors=${8:-192}:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
    -loop 0 "$OUT/$5"
  printf '  %-28s %6s KB\n' "$5" "$(( $(wc -c < "$OUT/$5") / 1024 ))"
}

png() { # png <repo> <path-in-repo> <filter> <output-name>
  local src="$TMP/$(basename "$2")"
  curl -fsSL "$RAW/$1/main/$2" -o "$src"
  ffmpeg -v error -y -i "$src" -vf "$3" -frames:v 1 "$OUT/$4"
  printf '  %-28s %6s KB\n' "$4" "$(( $(wc -c < "$OUT/$4") / 1024 ))"
}

echo "Building thumbnails into $OUT"

# MorphLab: the MuJoCo viewport while the learned controller walks the commanded 40 cm.
# (The command bar moves once the result text appears, so the crop keeps to the viewport.)
gif morphlab-ai docs/media/hero-ai-walk.gif \
  "crop=598:336:0:200,scale=640:360:flags=lanczos" 10 morphlab.gif 3.5 7 128

# Isaac uArm Twin: the full 3D cell, without the viewer toolbars.
gif isaac-uarm-twin docs/assets/twin-cycle.gif \
  "crop=1271:715:4:39,scale=640:360:flags=lanczos" 10 isaac-uarm-twin.gif

# HandPilot: real controller output, near-native crop.
gif handpilot docs/media/handpilot_demo.gif \
  "crop=820:461:0:4,scale=640:360:flags=lanczos" 12 handpilot.gif

# UR5 Singularity Atlas: padded (not cropped) to 16:9 on its white background.
gif ur5-singularity-atlas docs/media/lin_z_path.gif \
  "pad=720:405:0:22:color=0xffffff,scale=640:360:flags=lanczos" 12 ur5-singularity-atlas.gif

# Harmonic Digital Twin: padded to 16:9 on its off-white background.
gif harmonic-digital-twin docs/media/rig_twin.gif \
  "pad=880:495:0:63:color=0xfcfcfd,scale=640:360:flags=lanczos" 12 harmonic-digital-twin.gif

# TIA S7 Copilot: the dark dashboard, padded to 16:9 on its own navy background.
png tia-s7-copilot docs/assets/dashboard-dark.png \
  "pad=2400:1350:120:0:color=0x000028,scale=960:540:flags=lanczos" tia-s7-copilot.png

echo "Done."
