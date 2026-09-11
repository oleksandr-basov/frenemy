#!/bin/bash
# Builds dist/<name>-<edition>-<version>.mcaddon, the Ukrainian and English
# editions. Meant for installing on a tablet; development does not need it:
# there the packs are copied to the development folders by sync.ps1 (which
# always carries the Ukrainian voice).
#
#   ./build.sh                 every add-on, both editions
#   ./build.sh bedrock         a single add-on, both editions
#
# The editions differ ONLY in voice-over, pack names and UUIDs. The English
# one is built from the same packs with the voice wavs swapped from
# art/voice/en/ and its own UUIDs: the game imports a pack by the pair
# "UUID + version", and without separate UUIDs the two editions could not
# coexist. Synthesized effects (transform_*) are shared.
#
# The version comes from the VERSION file and is stamped into the COPIES of
# the manifests inside dist/. The source manifests stay at 1.0.0 and do not
# add noise to diffs. Bump VERSION before every hand-over to the tablet,
# otherwise the game reports "duplicate pack detected".
set -euo pipefail
cd "$(dirname "$0")"

VER="$(tr -d '[:space:]' < VERSION)"

ADDONS=("$@")
if [ ${#ADDONS[@]} -eq 0 ]; then
  ADDONS=()
  for found in */behavior_pack/manifest.json; do ADDONS+=("${found%%/*}"); done
fi

mkdir -p dist

for ADDON in "${ADDONS[@]}"; do
  # The archive name lives here, not in a file inside the add-on: Mojang's
  # validator treats any foreign file in the pack folder as garbage and
  # fails Project Integrity.
  case "$ADDON" in
    bedrock) SLUG=frenemy ;;
    *) echo "no archive name known for $ADDON, add a case to build.sh" >&2
       exit 1 ;;
  esac

  for EDITION in ua en; do
    rm -rf "dist/$SLUG" && mkdir -p "dist/$SLUG"
    cp -R "$ADDON/behavior_pack" "dist/$SLUG/${SLUG}_bp"
    cp -R "$ADDON/resource_pack" "dist/$SLUG/${SLUG}_rp"

    if [ "$EDITION" = en ]; then
      # Voice swap. Nothing here may be skipped quietly: a missing English
      # set is a broken build, not a reason to ship the Ukrainian voice.
      [ -d art/voice/en ] || { echo "no art/voice/en, run ./art/voices.sh first" >&2; exit 1; }
      for sub in friend monster; do
        for f in art/voice/en/"$sub"/*.wav; do
          [ -e "$f" ] || { echo "no wav files in art/voice/en/$sub" >&2; exit 1; }
          cp "$f" "dist/$SLUG/${SLUG}_rp/sounds/$sub/$(basename "$f")"
        done
      done
    fi

    python3 - "$VER" "$EDITION" "dist/$SLUG/${SLUG}_bp/manifest.json" "dist/$SLUG/${SLUG}_rp/manifest.json" <<'PY'
import json, re, sys

version = [int(part) for part in sys.argv[1].split('.')]
edition = sys.argv[2]

# The English edition is a separate package with its own UUIDs. The Ukrainian
# one keeps the originals: existing worlds already bind the pack under them,
# and a world binds packs by UUID.
UUIDS_EN = {
    '8e2f3ff2-73f3-41d8-bded-ce38f7163c81': '061adcc3-fb19-412b-a072-958090511798',
    '074d2b04-1b8f-40b4-a986-2b337e6d5960': '9cd05156-a1a6-4431-91e0-74b204193963',
    'de161483-0b8e-41ad-8dd6-d48f3bab00c7': '3719972f-0a76-40af-ba4b-65b3a55c80b5',
    '9c56a413-05bb-4af0-ab87-464ff417366a': 'a52cd34d-1590-454e-abff-82b7762e591d',
    '14262c90-5d89-4185-aa4c-16239cc3f4c0': '58a2aeef-7519-4b4e-9b54-fd1d4b401c67',
}
NAMES_EN = {
    'Frenemy (поведінка)': ('Frenemy (Behavior)',
                            'Companion logic and its transformations. Idea: Basov Danylo'),
    'Frenemy (вигляд)': ('Frenemy (Look)',
                         'Model, textures and render controllers. Idea: Basov Danylo'),
}
AUTHORS_EN = ['Basov Danylo', 'Oleksandr Basov']

for path in sys.argv[3:]:
    manifest = json.load(open(path))
    if edition == 'en':
        name = manifest['header']['name']
        assert name in NAMES_EN, (
            'no English name known for pack "%s", extend NAMES_EN in build.sh' % name)
        manifest['header']['name'], manifest['header']['description'] = NAMES_EN[name]
        manifest['metadata'] = {'authors': AUTHORS_EN}
        blob = json.dumps(manifest, ensure_ascii=False)
        for old, new in UUIDS_EN.items():
            blob = blob.replace(old, new)
        # Every UUID in the manifest must be known to the map: a new module or
        # a regenerated UUID would otherwise ship shared with the Ukrainian
        # edition, and the game would treat both editions as one pack.
        leftover = [u for u in re.findall(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', blob)
            if u not in UUIDS_EN.values()]
        assert not leftover, (
            'manifest has UUIDs outside UUIDS_EN: %s, extend the map in build.sh' % leftover)
        manifest = json.loads(blob)
    manifest['header']['version'] = version
    # The version in the NAME is a delivery check by eye: the game's pack list
    # shows at once which build is active. A week was once lost fighting a
    # three-day-old pack that looked identical to the new one in the UI.
    manifest['header']['name'] += ' v' + sys.argv[1]
    for module in manifest.get('modules', []):
        module['version'] = version
    # The dependency version must match the other pack's version, otherwise
    # the game will not link the packs. The uuid check guards script
    # dependencies, which are given by module_name and carry no version.
    for dependency in manifest.get('dependencies', []):
        if 'uuid' in dependency:
            dependency['version'] = version
    json.dump(manifest, open(path, 'w'), ensure_ascii=False, indent=2)
PY

    # Dot files from the Parallels network share end up inside the pack and
    # break the import.
    find "dist/$SLUG" -name '.DS_Store' -delete
    rm -f "dist/$SLUG-$EDITION-$VER.mcaddon"
    (cd "dist/$SLUG" && zip -qr "../$SLUG-$EDITION-$VER.mcaddon" . -x '.*' '*/.*')
    rm -rf "dist/$SLUG"
    echo "done: dist/$SLUG-$EDITION-$VER.mcaddon"
  done
done
