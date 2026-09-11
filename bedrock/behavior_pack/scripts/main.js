// Add-on scripts. Stable @minecraft/server: no experimental toggles.
//
// 1) Starter egg: every player gets one on first join, in Survival too.
// 2) Sound director: the ONLY source of voice lines. The JSON sound
//    mechanisms (ambient_sound_interval, on_damage_sound_event) are gone
//    from the entities: the ambient timer knew no context and could greet
//    cheerfully right after a slap, and hits in some states stayed mute.
//    Now:
//    - a hurt line plays on EVERY player hit (damage_sensor sends a
//      scriptevent even when the damage itself is cancelled), with an
//      anti-spam guard against rapid clicks;
//    - a hit on an entity trembling before a transformation sounds muffled
//      (pitch 0.8);
//    - after a hit comes the "sulk": no ambient line for 9 seconds, no
//      "Guess who?" right after a slap;
//    - ambient is picked by form (variant) with the intervals the JSON used
//      to have, plus a greeting 3-7 s after an entity appears near a player.
//    Transformation sounds stay on minecraft:transformation, the tame song
//    and the giggle in animation keyframes: their timing is exact as is.
import { world, system, ItemStack } from '@minecraft/server';

// ── Starter egg ─────────────────────────────────────────────────────
const EGG = 'frenemy:friend_spawn_egg';
// A NEW generation of the tag: the 2.6.0 handout was silent (no chat line),
// and a world could be left tagged but without a noticed egg. Renaming the
// tag hands the egg out once more to everyone, such worlds included.
// Hand it out again by hand: /tag @s remove frenemy_starter_egg
const EGG_TAG = 'frenemy_starter_egg';

function giveStarterEgg(player) {
  const inventory = player.getComponent('minecraft:inventory');
  const container = inventory && inventory.container;
  if (!container) return;
  try {
    const leftover = container.addItem(new ItemStack(EGG, 1));
    // A full inventory: addItem returned a remainder, not counted as given,
    // the guard retries once a slot frees up.
    if (leftover) return;
    player.addTag(EGG_TAG);
    try { player.sendMessage({ translate: 'frenemy.starter_egg' }); } catch (e) { }
    console.warn('[frenemy] starter egg given to ' + player.name);
  } catch (error) {
    console.warn('[frenemy] starter egg failed: ' + error);
  }
}

// Immediate handout on join, and the credits line on every join: the
// author asked for his name to be visible everywhere, the game included.
world.afterEvents.playerSpawn.subscribe(({ player, initialSpawn }) => {
  if (!initialSpawn) return;
  try { player.sendMessage({ translate: 'frenemy.credits' }); } catch (e) { }
  if (!player.hasTag(EGG_TAG)) giveStarterEgg(player);
});

// ...and a guard for when the join event is missed (the host of a
// single-player world may spawn before the script subscribes).
system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    if (!player.hasTag(EGG_TAG)) giveStarterEgg(player);
  }
}, 60);

// ── Sound director ──────────────────────────────────────────────────
// Line sets by form. Intervals in seconds, the same ones
// ambient_sound_interval used to have, so the character of speech is unchanged.
const VOICE = {
  'frenemy:friend': {
    hurt: 'friend.ouch',
    byVariant: [
      { sound: 'friend.hello', base: 10, spread: 6 },
      { sound: 'friend.dark', base: 8, spread: 4 },
    ],
  },
  'frenemy:monster': {
    hurt: 'monster.ouch',
    byVariant: [
      { sound: 'monster.calm', base: 12, spread: 6 },
      { sound: 'monster.rage', base: 3.5, spread: 2 },
    ],
  },
  'frenemy:shade': {
    hurt: 'monster.ouch',
    byVariant: [
      { sound: 'shade.whisper', base: 7, spread: 3 },
    ],
  },
};

// The fourth form. Hits on the ENRAGED monster accumulate: three within six
// seconds, the body gives way and snaps into the Shade.
const SNAP_HITS = 3;
const SNAP_WINDOW_MS = 6000;

const HURT_COOLDOWN_MS = 600;   // rapid clicks do not become a choir
const SULK_SILENCE_MS = 9000;   // the "sulk": ambient silence after a hit
const HEARING_RANGE = 24;       // no players nearby, do not play into the void

// The director's memory for a game session: entity.id -> { nextAt, lastHurtAt }.
// After re-entering the world it starts from scratch, harmless.
const state = new Map();

function variantOf(entity) {
  try {
    const component = entity.getComponent('minecraft:variant');
    return component ? component.value : 0;
  } catch (error) {
    return 0;
  }
}

function play(entity, sound, pitchBase) {
  const pitch = pitchBase * (0.95 + Math.random() * 0.1);
  try {
    entity.dimension.playSound(sound, entity.location, { volume: 1.8, pitch });
  } catch (error) {
    console.warn('[frenemy] play failed ' + sound + ': ' + error);
  }
}

// The moment of a hit arrives as a scriptevent from the entities' damage_sensor:
// frenemy:hurt, a regular hit, frenemy:hurt_shaking, a hit on a trembling one.
system.afterEvents.scriptEventReceive.subscribe((event) => {
  const entity = event.sourceEntity;
  if (!entity) return;
  const now = Date.now();
  const s = state.get(entity.id) || {};

  if (event.id !== 'frenemy:hurt' && event.id !== 'frenemy:hurt_shaking') return;
  const voice = VOICE[entity.typeId];
  if (!voice) return;
  if (s.lastHurtAt && now - s.lastHurtAt < HURT_COOLDOWN_MS) return;
  s.lastHurtAt = now;
  play(entity, voice.hurt, event.id === 'frenemy:hurt_shaking' ? 0.8 : 1.0);
  s.nextAt = Math.max(s.nextAt || 0, now + SULK_SILENCE_MS);

  // Hitting an ALREADY enraged monster tests it to breaking point: three
  // hits in a row, and the body crumbles into the Shade.
  if (entity.typeId === 'frenemy:monster' && variantOf(entity) === 1) {
    if (!s.rageHitAt || now - s.rageHitAt > SNAP_WINDOW_MS) s.rageHits = 0;
    s.rageHitAt = now;
    s.rageHits = (s.rageHits || 0) + 1;
    if (s.rageHits >= SNAP_HITS) {
      s.rageHits = 0;
      try { entity.triggerEvent('monster:snap'); } catch (error) { }
    }
  }
  state.set(entity.id, s);
});

system.runInterval(() => {
  const now = Date.now();
  let dimension;
  try { dimension = world.getDimension('overworld'); } catch (error) { return; }
  for (const type of Object.keys(VOICE)) {
    let entities;
    try { entities = dimension.getEntities({ type }); } catch (error) { continue; }
    for (const entity of entities) {
      // Each entity in its own try: one "rotten" entity (say, at the edge of
      // an unloading chunk) must not silence everyone else's lines.
      try {
        let s = state.get(entity.id);
        if (!s) {
          // The first line is a quick greeting, then the usual rhythm.
          s = { nextAt: now + 3000 + Math.random() * 4000 };
          state.set(entity.id, s);
          continue;
        }
        if (now < s.nextAt) continue;
        const listeners = dimension.getPlayers({ location: entity.location, maxDistance: HEARING_RANGE });
        if (listeners.length === 0) {
          s.nextAt = now + 4000;
          continue;
        }
        const set = VOICE[type].byVariant[variantOf(entity)] || VOICE[type].byVariant[0];
        play(entity, set.sound, 1.0);
        s.nextAt = now + (set.base + (Math.random() * 2 - 1) * set.spread) * 1000;
      } catch (error) {
        console.warn('[frenemy] ambient skip (' + type + '): ' + error);
      }
    }
  }
}, 20);
