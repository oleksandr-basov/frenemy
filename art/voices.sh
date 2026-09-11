#!/bin/bash
# Every voice line of both languages in one list. Run: ./art/voices.sh
#
# This exists because otherwise the text of a line lives only inside a wav:
# the file is there, but what it says and in what tone can no longer be
# recovered or corrected. Here one line is one phrase, and everything can be
# re-recorded with a single command.
#
# The Ukrainian track is written straight into the pack, that is what plays
# in the development loop. The English one goes to art/voice/en/, from where
# build.sh swaps it into the English edition. Both languages are recorded by
# ONE call of `line`, so the lists cannot drift apart; check.sh additionally
# compares the file sets.
#
# The English text is not a translation but an independent phrase of the
# same spirit. No personal names and no rude words: the add-on is public.
#
# The pitches are the character arc, not decoration:
#   1.35   the white ball, bright and kind
#   0.72   the dark ball: the same voice, but something is already wrong
#   0.55   the calm monster, low and insinuating
#   demon  the enraged monster: two voice layers + echo (see make_voice.sh)
#
# A real voice instead of the synthesizer is much funnier. For monster lines
# OUT_DIR is mandatory (without it the recording silently lands in friend/):
#   OUT_DIR=bedrock/resource_pack/sounds/monster \
#     ./art/make_voice.sh rec rage1 demon        record from the microphone
#   OUT_DIR=bedrock/resource_pack/sounds/monster \
#     ./art/make_voice.sh file rage1 demon ~/Desktop/recording.m4a
set -euo pipefail
cd "$(dirname "$0")/.."

UA_VOICE=Lesya      # one voice for all four stages: the monster IS the Friend
EN_VOICE=Samantha   # clean diction: recognizable both at 1.35 and in the bass at 0.55

DIR=friend
line() { # name pitch "Ukrainian text" "English text"
  OUT_DIR="bedrock/resource_pack/sounds/$DIR" \
    ./art/make_voice.sh say "$1" "$2" "$UA_VOICE" "$3"
  OUT_DIR="art/voice/en/$DIR" VOICE_TAG=en- \
    ./art/make_voice.sh say "$1" "$2" "$EN_VOICE" "$4"
}

# ── The white ball: a kind friend ────────────────────────────────────
line hello1 1.35 "Привіт! Це я! Знову я!"   "Guess who? Me again!"
line hello2 1.35 "Гайда на пригоди!"        "Adventure won't find itself!"
line hello3 1.35 "Куди ти — туди і я!"      "Where you go, I go!"

# The squeak at the moment of a hit
line ouch1 1.35 "Ай! Ти чого?!"             "Ow! Rude!"
line ouch2 1.35 "Ой! Це не обіймашки!"      "Hey! Not a hug!"

# The tame celebration song, plays from a keyframe of the backflip animation
line tame1 1.35 "Смакота! Тепер ми назавжди!" "Yum! Friends forever!"

# Nose boop (sneak + tap): a chain of three replies and a laugh on the third.
# Boops are played by play_sounds in interact, the laugh by the giggle keyframe.
line boop1 1.35 "Іще!"            "Again!"
line boop2 1.35 "Хі-хі!"          "Hehe!"
line boop3 1.35 "Ой, лоскотно!"   "That tickles!"
line giggle 1.35 "Ха-ха-ха-ха! Ну все, все!" "Hahaha! Okay, okay, stop!"

# ── The dark ball: after the first hit ──────────────────────────────
line dark1 0.72 "Будь ласка... не бий..."       "Please... stop..."
line dark2 0.72 "Я вже не зовсім я..."          "I don't feel like me..."
line dark3 0.72 "Не буди в мені монстра..."     "Don't wake the monster in me..."

# ── The calm monster: low and insinuating ────────────────────────────
# calm1 is the same phrase as hello3: the Friend's bright line echoed in a dark bass.
# calm3 is the teaching hint about the torch, exactly one in the whole set.
DIR=monster
line calm1 0.55 "Куди ти — туди і я..."               "Where you go... I go..."
line calm2 0.55 "Побігаймо? Я все одно дожену..."     "Wanna play tag? I always win."
line calm3 0.55 "Сумуєш за другом? Запали смолоскип..." "Miss your friend? Light a torch..."

# The inner voice: now and then the Friend's own voice breaks through the
# bass, "the Friend never left". Pitch 1.35 ON PURPOSE: this is the Friend
# speaking from inside. The files sit in the monster.calm set at lower volume.
line inner1 1.35 "Я тут! Я нікуди не дівся!"  "I'm still in here!"
line inner2 1.35 "Не бійся. Це все ще я..."   "Don't be scared. It's still me."

# ── The enraged monster: the demon ──────────────────────────────────
line rage1 demon "Тікай! Тікай! Тікай!"        "Run! Run! Run!"
line rage2 demon "Я тебе бачу!"                "I see you!"
line rage3 demon "Ха-ха-ха-ха!"                "Mwa-ha-ha-ha!"
line rage4 demon "Тепер воджу я!"              "My turn to be it!"
line rage5 demon "Знайду навіть під ліжком!"   "I'll find you under the bed!"

# The demon at the moment of a hit: snaps back, but it hurts too
line mouch1 demon "Ай! Мені зовсім не боляче!" "Ow! That didn't even hurt!"
line mouch2 demon "Ай! Рогам же боляче!"       "Ow! Right in the horns!"

# ── The Shade: what remains if you keep hitting ─────────────────────
line shade1 demon "Я — те, що лишилось..."  "I am what remains..."
line shade2 demon "Тс-с-с... я поруч..."    "Hush... I'm right here..."
line shade3 demon "Скоро спіймаю..."        "Gotcha soon..."
