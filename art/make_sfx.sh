#!/bin/bash
# Synthesizes the transformation sound effects. Run: ./art/make_sfx.sh
#
# Voices come from speech via make_voice.sh; this is pure ffmpeg synthesis:
# the rising hum before a transformation, the thump at the moment of it, and
# the "exhale" of turning back into the ball. Everything is reproducible
# from this file.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=bedrock/resource_pack/sounds/friend
mkdir -p "$OUT"

# The hum before a transformation: a low tone creeping up (55 -> ~150 Hz,
# quadratically), rustle on top, and a tremolo over everything. 3.4 s, the
# length of the transformation delay.
ffmpeg -hide_banner -loglevel error -y -filter_complex "\
aevalsrc='0.5*sin(2*PI*(55+9*t*t)*t)+0.25*sin(2*PI*(110+18*t*t)*t)':d=3.4:s=44100[tone];\
anoisesrc=d=3.4:c=brown:r=44100:a=0.35[noise];\
[tone][noise]amix=inputs=2:normalize=0,tremolo=f=7:d=0.6,\
afade=t=in:d=0.4,afade=t=out:st=3.2:d=0.2,\
volume=2.6,alimiter=limit=0.92" \
  -ac 1 -ar 44100 -c:a pcm_s16le "$OUT/transform_rise.wav"

# The transformation thump: a dull bass with a fast decay plus a short burst of noise.
ffmpeg -hide_banner -loglevel error -y -filter_complex "\
aevalsrc='0.9*sin(2*PI*(42+180*exp(-9*t))*t)*exp(-2.2*t)':d=1.6:s=44100[thump];\
anoisesrc=d=0.25:c=white:r=44100:a=0.5[crack];\
[crack]afade=t=out:st=0.02:d=0.22[crackf];\
[thump][crackf]amix=inputs=2:normalize=0,\
aecho=0.7:0.5:60:0.25,afade=t=out:st=1.3:d=0.3,\
volume=2.6,alimiter=limit=0.92" \
  -ac 1 -ar 44100 -c:a pcm_s16le "$OUT/transform_boom.wav"

# The reverse transformation: the same hum backwards and softer, tension
# fades, the Friend comes back.
ffmpeg -hide_banner -loglevel error -y -i "$OUT/transform_rise.wav" \
  -af "areverse,volume=1.6,alimiter=limit=0.92,afade=t=out:st=2.6:d=0.6" \
  -ac 1 -ar 44100 -c:a pcm_s16le "$OUT/transform_calm.wav"

# ── Leitmotif of the four forms ────────────────────────────────────
# One four-note melody that "slides down" along the arc: the white ball rings
# it in major (do-mi-sol-mi), the dark one in minor an octave lower, the calm
# monster lower and slower still, the enraged one growls it in the bass.
# The files are mixed into the ambient sets in sound_definitions.json: the
# engine picks a random file from a set, so the motif plays as a rare
# "song" of the form. Each note starts at its moment S and rings with decay
# until the end, notes overlap, like a bell.
OUTM=bedrock/resource_pack/sounds/monster
mkdir -p "$OUTM"

theme() { # file  d  decay  volume  f1 s1  f2 s2  f3 s3  f4 s4  post-processing
  local file=$1 dur=$2 dk=$3 vol=$4; shift 4
  local expr="" f s
  while [ $# -gt 1 ]; do
    f=$1; s=$2; shift 2
    [ -n "$expr" ] && expr="$expr+"
    expr="${expr}sin(2*PI*$f*t)*exp(-$dk*(t-$s))*gte(t,$s)"
  done
  ffmpeg -hide_banner -loglevel error -y \
    -filter_complex "aevalsrc='0.35*($expr)':d=$dur:s=44100,$1,volume=$vol,alimiter=limit=0.92,afade=t=out:st=$(awk -v d="$dur" 'BEGIN{printf "%.2f", d-0.3}'):d=0.3" \
    -ac 1 -ar 44100 -c:a pcm_s16le "$file"
}

# The white ball: major, a bell (do-mi-sol-mi of the sixth octave)
theme "$OUT/theme.wav"        2.0 5 2.0 \
  1046.5 0.0  1318.5 0.3  1568.0 0.6  1318.5 0.9 \
  "aecho=0.5:0.3:90:0.18"
# The dark ball: the same motif in minor an octave lower, slower
theme "$OUT/theme_dark.wav"   2.8 4 2.0 \
  523.25 0.0  622.25 0.42  784.0 0.84  622.25 1.26 \
  "aecho=0.6:0.4:120:0.25,tremolo=f=5:d=0.3"
# The calm monster: another octave down, insinuating
theme "$OUTM/theme_calm.wav"  3.4 3 2.2 \
  261.63 0.0  311.13 0.55  392.0 1.1  311.13 1.65 \
  "aecho=0.6:0.45:160:0.3,tremolo=f=4:d=0.5"
# The enraged one: bass, fast, overdriven, with a growling tremolo
theme "$OUTM/theme_rage.wav"  1.7 7 3.4 \
  130.81 0.0  155.56 0.22  196.0 0.44  155.56 0.66 \
  "tremolo=f=11:d=0.7,aecho=0.5:0.3:50:0.2"

for f in "$OUT/transform_rise" "$OUT/transform_boom" "$OUT/transform_calm" \
         "$OUT/theme" "$OUT/theme_dark" "$OUTM/theme_calm" "$OUTM/theme_rage"; do
  printf "%s  %s s\n" "${f#bedrock/resource_pack/sounds/}" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f.wav" | cut -c1-4)"
done
