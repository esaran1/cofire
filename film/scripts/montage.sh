#!/usr/bin/env bash
# Tile up to nine review stills into one image: montage.sh OUT.png a.png b.png ...
set -euo pipefail
out=$1; shift
args=(); fl=""; i=0
for f in "$@"; do args+=(-i "$f"); fl+="[$i]scale=640:360[v$i];"; i=$((i+1)); done
while [ $i -lt 9 ]; do args+=(-f lavfi -i "color=c=black:s=640x360:d=1"); fl+="[$i]null[v$i];"; i=$((i+1)); done
/opt/homebrew/bin/ffmpeg -loglevel error -y "${args[@]}" -frames:v 1 -filter_complex "${fl}[v0][v1][v2]hstack=3[r1];[v3][v4][v5]hstack=3[r2];[v6][v7][v8]hstack=3[r3];[r1][r2][r3]vstack=3" "$out"
