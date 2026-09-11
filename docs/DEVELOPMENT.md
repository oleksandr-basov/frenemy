# Development

How the add-on is built, checked and delivered. Player-facing docs are in
[README.md](../README.md) (English) and [README.uk.md](../README.uk.md) (Ukrainian).

## Layout

|Path|What it is|
|-|-|
|`bedrock/`|the whole add-on: Friend, Monster, Shade and the transformations between them|
|`bedrock/behavior_pack/scripts/main.js`|starter egg and the sound director (stable `@minecraft/server`)|
|`art/`|generators for the model, textures and voice; English voice tracks|
|`art/preview/`|renders of the models: pictures, not sources, but always look at them|
|`docs/ideas.md`|feature roadmap (Ukrainian)|
|`docs/publish/`|texts and checklist for MCPEDL|
|`VERSION`|the project version, one line; bump before every hand-over|
|`check.sh`|validation without launching the game|
|`build.sh`|builds both editions into `dist/`|
|`sync.ps1`|run INSIDE Windows: copies the packs to Minecraft's development folders|

## Tools

**VS Code** with the Blockception extension knows the schemas of every Bedrock
file: it suggests component names, highlights typos in `minecraft:behavior.*`
and complains about unknown fields as you type. Project settings are in
`.vscode/`.

**Blockbench** opens `bedrock/resource_pack/models/entity/friend.geo.json`
directly: for a human to poke the model. The geometry is written by
`art/make_friend.py`; run it after a manual edit and the edit silently
disappears. Either edit by hand and stop using the generator (then also save
a `.bbmodel` in `art/`), or carry the numbers back into the generator.

## Check and build

```
./check.sh              validation without the game: Mojang's validator plus our cross-checks
./build.sh              builds dist/frenemy-{ua,en}-<version>.mcaddon
python3 art/make_friend.py           regenerate geometry and textures
python3 art/render_geo.py --all --clay   render every geometry to art/preview/
./art/voices.sh         re-record every voice line in both languages
./art/make_sfx.sh       re-synthesize transformation effects and the leitmotif
./art/make_icons.sh     re-render the pack icons from the models
```

The two editions differ only in voice wavs, pack names and UUIDs (the map
lives in `build.sh`). The Ukrainian voice sits in the pack; the English one in
`art/voice/en/` and is swapped in at build time. `check.sh` verifies that the
English set mirrors the pack.

## Hand-over to a tablet

1. Bump `VERSION` (otherwise Minecraft reports a duplicate pack).
2. `./build.sh`
3. Send the wanted `dist/*.mcaddon` over AirDrop, open it in Minecraft: both
   packs import by themselves.
4. In the world settings enable **both** packs: Behavior Packs and Resource Packs.
5. Restart the game fully after new sounds or manifest changes; after a JSON
   edit leaving to the menu and re-entering the world is enough.

No experimental toggles are needed or allowed.

## Checking in game

Enable the error log first, otherwise Bedrock breaks silently:
**Settings → Creator → Content Log GUI**. Enable **subtitles** there too: they
tell "the sound did not play" apart from "the event did not fire".

Fast loop (Windows in Parallels, packs edited on the Mac):

```
powershell -ExecutionPolicy Bypass -File \\Mac\Home\NotWork\frenemy\sync.ps1
```

Use a separate test world with cheats: cheats disable achievements for good,
so keep the real play world apart.

|Do|Expect|If not|
|-|-|-|
|`/summon frenemy:friend`|a white orb hovers, chirps|check the Content Log|
|hit the orb|squeaks, darkens, voice drops|colour unchanged: `variant`|
|poke it with a torch|white again (you may change your mind)| |
|hit the dark orb again|trembles 3.4 s under a hum, then BOOM: a monster|no trembling: `transformation`|
|`/gamemode s` (otherwise no attacks)| |mobs do not attack in Creative|
|monster born|black, red eyes, hunts and hits; touch hurts too|no hits: check the Content Log|
|wait 25 s|cooled: dark blue, sneaks after you, threatens in a bass| |
|hit the calm one|squeaks, runs, boils over, comes back angry| |
|three quick hits on the enraged one|1.6 s trembling: the Shade| |
|flower on the Shade|2.2 s: the white Friend is back (owner kept)| |
|torch on the calm monster|2.2 s trembling: the Friend is back| |

Attacks can only be tested in Survival. In Creative hostile mobs do not
target the player and damage does not go through: a "monster that does not
attack" in a Creative world looks exactly like a broken attack.

## What to change first

|Want|File|
|-|-|
|the look|`bedrock/resource_pack/models/entity/friend.geo.json` via `art/make_friend.py`|
|colours|`PALETTE` in `art/make_friend.py`|
|how long it trembles before transforming|`delay` of `minecraft:transformation` in `friend.json`|
|what brings it back|torch: `minecraft:interact` of the dark orb and the monster; flower: `shade.json`|
|what tames it|`minecraft:tameable`, the `tame_items` list|
|names in game|`bedrock/resource_pack/texts/*.lang`|
|what it says and in which voice|`art/voices.sh`: every line in one list|
|how long it flees before attacking|`minecraft:timer` in the `monster:scared` group|
|how long it stays angry|`minecraft:timer` in the `monster:angry` group|
|how hard it hits|`minecraft:attack` there: 3 now, one and a half hearts|
|how much touching the enraged one hurts|`minecraft:area_attack` there|
|hits needed to snap into the Shade|`SNAP_HITS` in `scripts/main.js`|
|ambient rhythm and the sulk after a hit|`VOICE` and `SULK_SILENCE_MS` in `scripts/main.js`|
|pack icons|`art/make_icons.sh`: renders of the models themselves|
