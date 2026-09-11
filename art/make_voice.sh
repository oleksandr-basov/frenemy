#!/bin/bash
# Prepares the Friend's voice lines for Bedrock.
#
#   ./art/make_voice.sh say  hello 1.35 Samantha "Hello! I am your friend."
#   OUT_DIR=bedrock/resource_pack/sounds/monster ./art/make_voice.sh say ...
#   ./art/make_voice.sh file hello 1.35 ~/Desktop/recording.m4a
#   ./art/make_voice.sh rec  hello 1.35            # microphone, Ctrl+C to stop
#
# Arguments: mode, file name, pitch shift, then voice + text or a recording path.
# Pitch shift: 1.0, as is, 1.35, the white ball, 0.72, the dark ball,
# 0.55, the calm monster, demon, the enraged one (two layers + echo, below).
# Duration does not change with the shift.
#
# Output: $OUT_DIR/<name>.wav, by default bedrock/resource_pack/sounds/friend/
# Format: mono, 44100 Hz, 16 bit, Bedrock reads wav directly.
# No ogg: Homebrew's ffmpeg is built without libvorbis, and the built-in
# vorbis encoder refuses mono ("only supports 2 channels"), producing an
# .ogg with FLAC inside that the game silently refuses to play.
# Stereo is not an option either, it is not positioned in space, the voice
# would sound inside the player's head rather than from the Friend.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:?mode: say | file | rec}"
NAME="${2:?file name without extension}"
PITCH="${3:-1.0}"

# The caller picks the destination: the Ukrainian voice goes straight into
# the pack, the English one into art/voice/en, where build.sh picks it up.
OUT="${OUT_DIR:-bedrock/resource_pack/sounds/friend}/$NAME.wav"
# VOICE_TAG keeps the raw caches of the two languages apart: without it the
# English take of a line would overwrite the Ukrainian .source.aiff.
RAW="art/sfx/${VOICE_TAG:-}$NAME.source"
mkdir -p "$(dirname "$OUT")" art/sfx

case "$MODE" in
  say)
    VOICE="${4:?voice: Lesya (uk) or Samantha (en)}"
    TEXT="${5:?line text}"
    say -v "$VOICE" -o "$RAW.aiff" "$TEXT"
    SRC="$RAW.aiff"
    ;;
  file)
    SRC="${4:?path to an audio file}"
    cp "$SRC" "$RAW.${SRC##*.}"
    ;;
  rec)
    echo "Speak. Ctrl+C to stop recording."
    # :0, the default microphone. List devices with:
    #   ffmpeg -f avfoundation -list_devices true -i ""
    ffmpeg -hide_banner -loglevel warning -f avfoundation -i ":0" -y "$RAW.wav" || true
    SRC="$RAW.wav"
    ;;
  *) echo "unknown mode: $MODE" >&2; exit 1 ;;
esac

# PITCH=demon is a special mode: the same line in two layers (0.62 and 0.45),
# mixed together and given a short echo. One low layer sounds like a slowed
# recording; two mismatched ones plus echo sound like a movie demon.
if [ "$PITCH" = "demon" ]; then
  ffmpeg -hide_banner -loglevel error -y -i "$SRC" -filter_complex "\
aresample=44100,asplit[a][b];\
[a]asetrate=44100*0.62,aresample=44100,atempo=1.6129[low];\
[b]asetrate=44100*0.45,aresample=44100,atempo=2.2222,volume=0.6[sub];\
[low][sub]amix=inputs=2:normalize=0,\
aecho=0.8:0.55:38|71:0.32|0.22,\
silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,\
areverse,silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,areverse,\
dynaudnorm=p=0.9,volume=2.2,alimiter=limit=0.92" \
    -ac 1 -ar 44100 -c:a pcm_s16le "$OUT"
  DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
  printf "%s  %.2f s  mono 44100  (demon)\n" "$OUT" "$DUR"
  exit 0
fi
# 1/PITCH for atempo, it restores the original duration after the shift.
BACK=$(awk -v p="$PITCH" 'BEGIN { printf "%.6f", 1 / p }')


# aresample=44100 at the START is mandatory: say outputs 22050 Hz, and without
# the resample asetrate=44100*p doubles the speed. A recorder outputs 48000,
# the same trouble the other way round.
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -af "\
aresample=44100,\
asetrate=44100*$PITCH,aresample=44100,atempo=$BACK,\
silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,\
areverse,silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,areverse,\
dynaudnorm=p=0.9,volume=2.2,alimiter=limit=0.92" \
  -ac 1 -ar 44100 -c:a pcm_s16le "$OUT"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
printf "%s  %.2f s  mono 44100\n" "$OUT" "$DUR"
