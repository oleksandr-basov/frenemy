#!/bin/bash
# Validates the add-ons with Mojang's official validator plus our own
# cross-checks. Catches what Bedrock breaks silently in game: broken texture,
# geometry and sound references, manifest drift, an entity without spawn rules,
# a typo in a bone name.
#
#   ./check.sh                 every add-on in the repository
#   ./check.sh bedrock         a single one
#
# Do not run `validate addon`: that is the strict Marketplace rule set, it
# demands creatorshortname_projectshortname namespaces and textures under an
# author subfolder. For a home add-on that is noise, not findings.
set -euo pipefail
cd "$(dirname "$0")"

# npm on this machine points at a corporate CodeArtifact registry with an
# expiring token. userconfig=/dev/null disables ~/.npmrc entirely; registry
# brings back the public npm.
export npm_config_registry=https://registry.npmjs.org
export npm_config_userconfig=/dev/null

ADDONS=("$@")
if [ ${#ADDONS[@]} -eq 0 ]; then
  ADDONS=()
  for found in */behavior_pack/manifest.json; do ADDONS+=("${found%%/*}"); done
fi

for ADDON in "${ADDONS[@]}"; do
  echo "── $ADDON ──"
  # mct writes its reports to out/. Left in place, the next run treats it as
  # a foreign folder inside the pack and fails Project Integrity.
  rm -rf "$ADDON/out" out

  # No -v: mct reads it as --version, prints the number and validates nothing.
  REPORT="$(npx -y @minecraft/creator-tools@0.17.7 validate -i "$ADDON" 2>&1 || true)"
  rm -rf "$ADDON/out" out
  # Successes are not printed: fifty lines of them drown the one real finding.
  # That is exactly how a one-way manifest dependency once slipped through.
  # Known false positives are muted by name so that a NEW one stays visible.
  # COMJSON134: wants uv_anim in the render controller; vanilla cow.v3 has none
  # ENTITYTYPE120, FORMATVER256, FORMATVER296, "raise format_version": low
  #               versions are deliberate, otherwise the add-on will not load
  #               on a tablet that lags behind the latest game build
  # FORMATVER216, "raise the animation version": vanilla uses 1.8.0 in 89 of
  #               96 files, so the recommendation contradicts the game itself
  # FORMATVER156, the same recommendation for recipes
  # PATHLENGTH104, an uppercase notes file in the add-on root; it belongs to
  #               the repository, not to the pack
  # UNLINK323 with minecraft:, the validator looks for vanilla recipe
  #               ingredients inside the pack; a typo in a frenemy: item stays visible
  KNOWN='COMJSON134|ENTITYTYPE120|FORMATVER156|FORMATVER216|FORMATVER256|FORMATVER296|PATHLENGTH104|UNLINK323.*minecraft:'
  echo "$REPORT" | grep -vE "^npm (warn|notice)|TESTSUCCESS|UNKNOWN:|Processing project|in \(-i\):|$KNOWN" || true
  # No TESTSUCCESS at all means the validator never ran (npx failed to
  # download, registry unreachable): the || true above swallows its exit
  # code, and without this gate the script would lie that all is well.
  if echo "$REPORT" | grep -qE 'TESTFAIL|\[ERROR' || ! echo "$REPORT" | grep -q TESTSUCCESS; then
    echo "Mojang validator complains or did not run, see the lines above" >&2
    exit 1
  fi

  python3 - "$ADDON" <<'PY'
import glob
import json
import os
import re
import sys

addon = sys.argv[1]


def path(*parts):
    return os.path.join(addon, *parts)


def load(name):
    with open(name, encoding='utf-8') as handle:
        return json.load(handle)


bp = load(path('behavior_pack/manifest.json'))
rp = load(path('resource_pack/manifest.json'))

# The dependency must go BOTH ways. A one-way link means the packs do not
# travel together: enabling one does not pull in the other, and a player
# joining over the network gets an incomplete set, the entity is invisible.
assert rp['header']['uuid'] in [d.get('uuid') for d in bp.get('dependencies', [])], (
    'behavior_pack does not depend on the resource pack, logic without looks')
assert bp['header']['uuid'] in [d.get('uuid') for d in rp.get('dependencies', [])], (
    'resource_pack does not depend on the behavior pack, a second player will not see the entity')

# A module with the -beta suffix enables the Beta APIs experiment, which
# disables achievements in the world for good. Stable @minecraft/server
# needs no toggle.
for kind, manifest in (('behavior', bp), ('resource', rp)):
    for dependency in manifest.get('dependencies', []):
        assert '-beta' not in str(dependency.get('version', '')), (
            '%s pack depends on a beta module %s, this enables an experiment '
            'and disables achievements forever' % (kind, dependency))

geometries = {}
for source in glob.glob(path('resource_pack/models/entity/*.geo.json')):
    for model in load(source)['minecraft:geometry']:
        geometries[model['description']['identifier']] = {b['name'] for b in model['bones']}

controllers = {}
for source in glob.glob(path('resource_pack/render_controllers/*.json')):
    controllers.update(load(source)['render_controllers'])

animations = {}
for source in glob.glob(path('resource_pack/animations/*.json')):
    animations.update(load(source).get('animations', {}))
for source in glob.glob(path('resource_pack/animation_controllers/*.json')):
    animations.update(load(source).get('animation_controllers', {}))

entities = {}
variants = {}
for source in glob.glob(path('behavior_pack/entities/*.json')):
    entity = load(source)['minecraft:entity']
    identifier = entity['description']['identifier']
    entities[identifier] = source
    # How many looks the entity has: variant lives both in the shared
    # components and in groups, and the controller arrays must cover them all.
    holders = [entity.get('components', {})] + list(entity.get('component_groups', {}).values())
    variants[identifier] = max(
        [holder['minecraft:variant']['value'] for holder in holders
         if 'minecraft:variant' in holder] or [0])

seen = set()
client = glob.glob(path('resource_pack/entity/*.entity.json'))
assert client, 'the resource pack has no client entity at all'
for source in client:
    description = load(source)['minecraft:client_entity']['description']
    seen.add(description['identifier'])

    for identifier in description['geometry'].values():
        assert identifier in geometries, (
            '%s references geometry %s that is not in the pack; available: %s'
            % (source, identifier, ', '.join(sorted(geometries))))
    for texture in description['textures'].values():
        assert os.path.exists(path('resource_pack', texture + '.png')), (
            'missing texture file: %s' % path('resource_pack', texture + '.png'))

    bones = set()
    for identifier in description['geometry'].values():
        bones |= geometries[identifier]

    # Molang needs declared variables: an expression with an undeclared v.*
    # silently evaluates to zero, and the bone simply never shows.
    declared = set()
    for line in description.get('scripts', {}).get('pre_animation', []):
        if line.strip().startswith(('variable.', 'v.')):
            declared.add(line.split('=')[0].strip().split('.', 1)[1])

    used = set()
    for name in description['render_controllers']:
        if isinstance(name, dict):
            name = list(name)[0]
        assert name in controllers, (
            '%s asks for controller %s that is not in the pack' % (source, name))
        controller = controllers[name]

        # Bone names are a contract between the geometry generator and
        # part_visibility. Rename a bone in art/make_friend.py and the face
        # freezes in one expression, neither the game nor the log says a word.
        for rule in controller.get('part_visibility', []):
            for bone, expression in rule.items():
                assert bone == '*' or bone in bones, (
                    'part_visibility references bone "%s" that is not in the geometry; '
                    'available: %s' % (bone, ', '.join(sorted(bones))))
                if isinstance(expression, str):
                    used |= set(re.findall(r'(?:variable|v)\.([a-z_0-9]+)', expression))

        # The controller addresses geometry, texture and material by short
        # name, Geometry.night, Texture.day. The names are declared in the
        # client entity. A typo is not an error: the engine takes the first
        # thing it finds and draws the wrong one.
        lines = [controller.get('geometry', '')] + list(controller.get('textures', []))
        for rule in controller.get('materials', []):
            lines += [v for v in rule.values() if isinstance(v, str)]
        for group in controller.get('arrays', {}).values():
            for array in group.values():
                lines += array
        for kind, names in (('Geometry', description['geometry']),
                            ('Texture', description['textures']),
                            ('Material', description['materials'])):
            for short in re.findall(r'%s\.([a-zA-Z_0-9]+)' % kind, ' '.join(lines)):
                assert short in names, (
                    'controller asks for %s.%s, but the client entity declares only: %s'
                    % (kind, short, ', '.join(sorted(names))))

    # Animation fails the quietest of all: a missing bone, an undeclared
    # variable or a name from the wrong list gives neither an error nor motion.
    named = description.get('animations', {})
    for short, identifier in named.items():
        assert identifier in animations, (
            '%s: animation "%s" (%s) is neither in animations/ nor in animation_controllers/'
            % (source, short, identifier))
    for entry in description.get('scripts', {}).get('animate', []):
        short = list(entry)[0] if isinstance(entry, dict) else entry
        assert short in named, (
            '%s: scripts.animate asks for "%s", which description.animations lacks; '
            'available: %s' % (source, short, ', '.join(sorted(named)) or 'nothing'))
        identifier = named[short]
        for bone in animations[identifier].get('bones', {}):
            assert bone in bones, (
                '%s animates bone "%s" that is not in the geometry; available: %s'
                % (identifier, bone, ', '.join(sorted(bones))))
        used |= set(re.findall(r'(?:variable|v)\.([a-z_0-9]+)',
                               json.dumps(animations[identifier])))

    # The controller picks skin and shape by query.variant. If a group sets a
    # variant the array does not have, the engine silently takes whatever,
    # the monster gets angry and keeps its old colours.
    highest = variants.get(description['identifier'], 0)
    for name in description['render_controllers']:
        if isinstance(name, dict):
            name = list(name)[0]
        body = json.dumps(controllers[name], ensure_ascii=False)
        for group in controllers[name].get('arrays', {}).values():
            for array_name, array in group.items():
                if '%s[query.variant]' % array_name not in body:
                    continue
                assert len(array) > highest, (
                    '%s: %s has %d element(s), but component groups set variant '
                    'up to %d, the engine will silently pick the wrong one'
                    % (source, array_name, len(array), highest))

    missing = used - declared
    assert not missing, (
        '%s: animations and part_visibility read variables that pre_animation '
        'never declares: %s' % (source, ', '.join(sorted(missing))))

assert entities, 'the behavior pack has no entity at all'
assert set(entities) == seen, (
    'the packs disagree on entities: behavior %s, resources %s, logic without '
    'looks or looks without logic' % (sorted(entities), sorted(seen)))

# Without spawn rules an entity appears nowhere: is_spawnable only yields a
# creative-inventory egg, and /summon requires cheats.
rules = glob.glob(path('behavior_pack/spawn_rules/*.json'))
ruled = set()
for source in rules:
    identifier = load(source)['minecraft:spawn_rules']['description']['identifier']
    assert identifier in entities, (
        '%s describes %s, and the pack has no such entity' % (source, identifier))
    ruled.add(identifier)
for identifier in entities:
    assert identifier in ruled, (
        '%s has no spawn rules, it will never appear in the world' % identifier)

# Sound breaks silently: the game says nothing about a typo in a name or a
# missing file. A broken resource pack additionally mutes ALL sound in the game.
definitions_path = path('resource_pack/sounds/sound_definitions.json')
if os.path.exists(definitions_path):
    definitions = load(definitions_path)['sound_definitions']

    for key, definition in definitions.items():
        for sound in definition.get('sounds', []):
            name = sound['name'] if isinstance(sound, dict) else sound
            assert not name.endswith(('.wav', '.ogg', '.fsb')), (
                '%s: path %s carries an extension, the engine appends its own '
                'and the file will not be found' % (key, name))
            assert [ext for ext in ('.wav', '.ogg', '.fsb')
                    if os.path.exists(path('resource_pack', name + ext))], (
                'missing sound file %s.{wav,ogg,fsb}' % path('resource_pack', name))

    catalogue_path = path('resource_pack/sounds.json')
    if os.path.exists(catalogue_path):
        catalogue = load(catalogue_path)

        # begin_transform_sound / transformation_sound look the name up in
        # individual_event_sounds, NOT in sound_definitions: vanilla
        # convert_to_drowned and remedy have no definitions at all, only events.
        individual = catalogue.get('individual_event_sounds', {}).get('events', {})
        for source in glob.glob(path('behavior_pack/entities/*.json')):
            entity_json = json.dumps(load(source))
            for field in ('begin_transform_sound', 'transformation_sound'):
                for match in re.findall(r'"%s"\s*:\s*"([^"]+)"' % field, entity_json):
                    assert match in individual, (
                        '%s: %s "%s" is not declared in individual_event_sounds '
                        'of sounds.json, the transformation will be silent'
                        % (source, field, match))
        referenced = []
        for identifier, sounded in catalogue.get('entity_sounds', {}).get('entities', {}).items():
            assert identifier in entities, (
                'sounds.json voices %s, and the pack has no such entity' % identifier)
            referenced += list(sounded.get('events', {}).values())
        for event in catalogue.get('individual_event_sounds', {}).get('events', {}).values():
            referenced.append(event['sound'] if isinstance(event, dict) else event)
        for key in referenced:
            assert key in definitions, (
                'sounds.json references "%s", which sound_definitions.json lacks' % key)

    # Sounds played from animation keyframes: the client entity declares a
    # short name in sound_effects, and a typo in the long name is silence at
    # exactly the moment the animation was written for.
    for source in client:
        effects = load(source)['minecraft:client_entity']['description'].get('sound_effects', {})
        for short, key in effects.items():
            assert key in definitions, (
                '%s: sound_effects "%s" points at "%s", which sound_definitions.json lacks'
                % (source, short, key))

    # The English build swaps voice wavs for the set in art/voice/en, and that
    # set must mirror the pack: whatever is missing ships to English players
    # with the Ukrainian voice, silently. transform_* and theme_* are shared
    # wordless synthesis and need no English twin.
    if os.path.isdir('art/voice/en'):
        for sub in ('friend', 'monster'):
            pack_dir = path('resource_pack', 'sounds', sub)
            en_dir = os.path.join('art', 'voice', 'en', sub)
            if not os.path.isdir(pack_dir):
                continue
            want = {n for n in os.listdir(pack_dir)
                    if n.endswith('.wav') and not n.startswith(('transform', 'theme'))}
            have = ({n for n in os.listdir(en_dir) if n.endswith('.wav')}
                    if os.path.isdir(en_dir) else set())
            missing, extra = sorted(want - have), sorted(have - want)
            assert not missing and not extra, (
                'English voice set diverged from sounds/%s: missing %s, extra %s'
                % (sub, missing or 'nothing', extra or 'nothing'))

    # A subtitle without a translation line shows the raw key instead of text.
    translated = set()
    for language in load(path('resource_pack/texts/languages.json')):
        with open(path('resource_pack/texts/%s.lang' % language), encoding='utf-8') as handle:
            for line in handle:
                if '=' in line:
                    translated.add(line.split('=')[0].strip())
    for definition in definitions.values():
        subtitle = definition.get('subtitle')
        assert not subtitle or subtitle in translated, (
            'subtitle %s is not translated in any .lang file' % subtitle)

print('%s: manifests, geometry, textures, sound and spawn rules are consistent' % addon)
PY
done
