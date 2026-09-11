#!/usr/bin/env python3
"""Generates the Friend's geometry and textures, every form and every skin.

Run: python3 art/make_friend.py
Look at the result: python3 art/render_geo.py --all --clay

Writes straight into bedrock/resource_pack/. The output is committed: the
script exists so that shape, face and texture layout can never drift apart
by hand, not as a mandatory build step.

BALL. Built from cubes: Blockbench mesh tools export to poly_mesh, which is
poorly supported and out of the game's style. Roundness does not come from
layers alone, a layer is a box, and a box is square from above, so a ball
reads as a cube. Each layer is TWO crossed boxes, one wide along X and one
wide along Z: their union is an octagon, i.e. the corners are cut in both
planes.

MONSTER. The night form is the same ball raised to its own height and turned
into a head. Not a single ball dimension changes: the transformation must
read as "my Friend grew up", not "my Friend was swapped". Everything new (body,
neck, arms, horns) sits below and to the sides; the silhouette grows
twice as tall.

FACE. Zero-thickness planes in front of the ball, a vanilla trick
(creaking.geo.json has a 9x14x0 cube). Each expression lives in ITS OWN bone,
because part_visibility in the render controller toggles bones by name. Bone
names are identical in every form, so one controller serves them all. The
names are part of the contract with friend.render_controllers.json and may
only change in both places at once; check.sh verifies this.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from png import write_png

ROOT = pathlib.Path(__file__).resolve().parent.parent
RP = ROOT / "bedrock" / "resource_pack"

TEXTURE_SIZE = 128
DIAMETER = 12  # pixels; 16 pixels are one block, so the ball is three quarters of a block
FRONT = -DIAMETER / 2 - 0.05  # the face sits slightly in front of the surface, else z-fighting
LIFT = 15  # how far the ball is raised in the night form: legs, torso and neck

# (bottom Y, height, layer width), the 8-10-12-10-8 silhouette.
BANDS = [
    (0, 2, 8),
    (2, 2, 10),
    (4, 4, 12),
    (8, 2, 10),
    (10, 2, 8),
]

# How narrow the second box of a layer is. 2/3 gives a visible corner cut
# without turning the layer into a cross.
CROSS_RATIO = 2 / 3

# Bone -> face planes. Integer sizes: Bedrock does not understand fractional UVs
# everywhere. There is always an empty pixel between brows, eyes and mouth:
# without the gap three black spots merge into one, and instead of fright you
# get a blot. This only shows on a render; in JSON the numbers look fine.
FACE = [
    ("eyes_open", "eye", [
        ((-3, 5), (2, 2), 0),
        ((1, 5), (2, 2), 0),
    ]),
    ("eyes_closed", "eye", [
        ((-3, 6), (2, 1), 0),
        ((1, 6), (2, 1), 0),
    ]),
    ("eyes_worried", "eye", [
        ((-3, 5), (2, 3), 0),
        ((1, 5), (2, 3), 0),
    ]),
    ("brows", "brow", [
        ((-4, 9), (3, 1), 18),
        ((1, 9), (3, 1), -18),
    ]),
    ("mouth_line", "mouth", [
        ((-2.5, 3), (5, 1), 0),
    ]),
    ("mouth_open", "mouth", [
        ((-1.5, 2), (3, 2), 0),
    ]),
]

# The Shade's face: huge eyes, brows tilted outwards (anger, not fright), the
# mouth almost gone. Bone names are the same, the contract with the render
# controllers is shared by every form, and check.sh verifies it.
FACE_SHADE = [
    ("eyes_open", "eye", [
        ((-4, 4), (3, 3), 0),
        ((1, 4), (3, 3), 0),
    ]),
    ("eyes_closed", "eye", [
        ((-4, 5), (3, 1), 0),
        ((1, 5), (3, 1), 0),
    ]),
    ("eyes_worried", "eye", [
        ((-4, 4), (3, 4), 0),
        ((1, 4), (3, 4), 0),
    ]),
    ("brows", "brow", [
        ((-5, 8), (4, 1), -25),
        ((1, 8), (4, 1), 25),
    ]),
    ("mouth_line", "mouth", [
        ((-2, 2), (4, 1), 0),
    ]),
    ("mouth_open", "mouth", [
        ((-1, 1), (2, 2), 0),
    ]),
]

# Shading of solid parts: lighter on top, darker below, otherwise a flat fill
# reads as a flat spot, not a volume. Face planes are not shaded.
SHADES = {"top": 1.12, "side": 1.0, "bottom": 0.78}
SOLID = ("body", "shell", "horn")

PALETTE = {
    "friend_day": {
        "body": (238, 238, 242),
        "shell": (238, 238, 242),
        "horn": (238, 238, 242),
        "wing": (238, 238, 242),
        "eye": (58, 62, 78),
        "brow": (58, 62, 78),
        "mouth": (58, 62, 78),
    },
    "friend_night": {
        "body": (46, 49, 64),
        "shell": (26, 28, 38),
        "horn": (206, 198, 176),
        "wing": (36, 32, 48),
        "eye": (240, 226, 178),
        "brow": (150, 142, 118),
        "mouth": (150, 142, 118),
    },
    # The enraged form: body almost black, eyes red. One UV layout for every
    # texture, so any skin fits any geometry.
    "friend_angry": {
        "body": (24, 22, 28),
        "shell": (14, 13, 17),
        "horn": (188, 176, 166),
        "wing": (90, 20, 24),
        "eye": (236, 46, 32),
        "brow": (176, 52, 40),
        "mouth": (150, 34, 26),
    },
    # The Shade: a core blacker than night, shards a touch lighter, eyes
    # burning brighter than the enraged form.
    "friend_shade": {
        "body": (16, 14, 20),
        "shell": (30, 28, 36),
        "horn": (140, 130, 150),
        "wing": (30, 28, 36),
        "eye": (255, 64, 40),
        "brow": (208, 62, 46),
        "mouth": (160, 40, 30),
    },
}


def box(x, y, z, width, height, depth, tone=None):
    cube = {"origin": [x, y, z], "size": [width, height, depth]}
    if tone:
        cube["tone"] = tone
    return cube


def crossed(y, height, span):
    """A layer of two crossed boxes: wide along X and wide along Z."""
    narrow = max(2, int(round(span * CROSS_RATIO / 2)) * 2)
    return [box(-width // 2, y, -depth // 2, width, height, depth)
            for width, depth in ((span, narrow), (narrow, span))]


def build_ball(lift=0):
    return [box(c["origin"][0], c["origin"][1] + lift, c["origin"][2], *c["size"])
            for y, height, span in BANDS for c in crossed(y, height, span)]


def face_bones(parent, lift=0, spec=None, zoff=0):
    """One bone per expression; the render controller shows them one at a time.

    spec, which expression set to lay out (FACE or FACE_SHADE),
    zoff, shift of the whole mask along Z for heads carried forward."""
    front = FRONT + zoff
    bones = []
    for name, tone, planes in (spec or FACE):
        cubes = []
        for (x, y), (width, height), angle in planes:
            cube = box(x, y + lift, front, width, height, 0)
            if angle:
                cube["pivot"] = [x + width / 2, y + lift + height / 2, front]
                cube["rotation"] = [0, 0, angle]
            cubes.append(cube)
        bones.append({"name": name, "parent": parent, "tone": tone,
                      "pivot": [0, DIAMETER / 2 + lift, front], "cubes": cubes})
    return bones


def day_bones():
    return [
        {"name": "body", "pivot": [0, DIAMETER / 2, 0], "tone": "body",
         "cubes": build_ball()},
        {"name": "face", "parent": "body", "tone": "body", "cubes": [],
         "pivot": [0, DIAMETER / 2, FRONT]},
    ] + face_bones("face")


def night_bones():
    """Legs, torso, arms, neck, ball head and horns. Bottom to top.

    The monster walks on the ground, so it has legs rather than a tapering
    tail: a torso floating in the air and gliding over grass reads as a bug.
    Hands and feet are pale, matching the horns, then the silhouette
    assembles into a figure instead of a dark blob.

    Rotations around X and Y are kept to a minimum, and all of them small.
    The rotation sign in .geo.json was checked against the vanilla armadillo
    (a tail with rotation [29,0,0] points down and back), but the less you
    lean on it, the smaller the chance of seeing something in game that the
    render did not show.
    """
    bones = []
    for side, sign in (("left", 1), ("right", -1)):
        x = 0.5 if sign > 0 else -3.5
        bones.append({
            "name": "leg_%s" % side, "parent": "body", "tone": "shell",
            "pivot": [sign * 2, 5, 0],
            "cubes": [box(x, 1, -1.5, 3, 4, 3), box(x, 0, -1.5, 3, 1, 3, "horn")],
        })
    bones.insert(0, {"name": "body", "pivot": [0, 8, 0], "tone": "shell",
                     "cubes": crossed(8, 5, 8) + crossed(5, 3, 6)})
    bones.append({"name": "neck", "parent": "body", "pivot": [0, 13, 0], "tone": "shell",
                  "cubes": [box(-2, 13, -2, 4, 2, 4)]})
    for side, sign in (("left", 1), ("right", -1)):
        x = 4 if sign > 0 else -6
        bones.append({
            "name": "arm_%s" % side, "parent": "body", "tone": "shell",
            "pivot": [sign * 5, 13, 0], "rotation": [8, 0, sign * 7],
            "cubes": [box(x, 8, -1, 2, 5, 2), box(x, 5, -1, 2, 3, 2),
                      box(x, 4, -1, 2, 1, 2, "horn")],
        })
    bones.append({"name": "head", "parent": "neck", "tone": "body",
                  "pivot": [0, LIFT + DIAMETER / 2, 0], "cubes": build_ball(LIFT)})

    horns = []
    for sign in (1, -1):
        x = 2 if sign > 0 else -4
        horn = box(x, LIFT + 10, -1, 2, 4, 2)
        horn["pivot"] = [sign * 3, LIFT + 10, 0]
        horn["rotation"] = [0, 0, -22 * sign]
        horns.append(horn)
    bones.append({"name": "horns", "parent": "head", "tone": "horn", "cubes": horns,
                  "pivot": [0, LIFT + 10, 0]})

    bones.append({"name": "face", "parent": "head", "tone": "body", "cubes": [],
                  "pivot": [0, LIFT + DIAMETER / 2, FRONT]})
    return bones + face_bones("face", LIFT)


# Shards of the Shade's shell: (origin, size). Every shard* bone has its pivot
# at the core's centre, the client animation spins them along an orbit with
# a single rotation.
SHARDS = [
    ((13, 3, -2), (4, 3, 3)),
    ((-16, 7, -1), (3, 4, 3)),
    ((-3, 15, -13), (5, 3, 3)),
    ((1, -1, 12), (4, 2, 4)),
]


def wraith_bones():
    """The Shade: fourth form, the destruction branch. The body crumbled,
    what remains is the core ball (the very same, not a dimension changed),
    horns, huge eyes and shards of the old shell hanging around it. The arc
    closes its circle: ball -> body -> ball again, inside out."""
    bones = [
        {"name": "body", "pivot": [0, DIAMETER / 2, 0], "tone": "body",
         "cubes": build_ball()},
    ]
    for index, (origin, size) in enumerate(SHARDS, 1):
        bones.append({
            "name": "shard%d" % index, "parent": "body", "tone": "shell",
            "pivot": [0, DIAMETER / 2, 0],
            "cubes": [box(*origin, *size)],
        })
    horns = []
    for sign in (1, -1):
        x = 2 if sign > 0 else -4
        horn = box(x, 10, -1, 2, 4, 2)
        horn["pivot"] = [sign * 3, 10, 0]
        horn["rotation"] = [0, 0, -24 * sign]
        horns.append(horn)
    bones.append({"name": "horns", "parent": "body", "tone": "horn",
                  "cubes": horns, "pivot": [0, 10, 0]})
    bones.append({"name": "face", "parent": "body", "tone": "body", "cubes": [],
                  "pivot": [0, DIAMETER / 2, FRONT]})
    return bones + face_bones("face", 0, FACE_SHADE)


DRAGON_HEAD_LIFT = 16   # how far the dragon's ball head is raised
DRAGON_HEAD_ZOFF = -21  # and how far it is carried forward


def dragon_bones():
    """The Dragon: a shelved draft (removed from the add-on on 9 September
    2026), the care branch, a tamed monster GROWN UP. The head is still the
    same ball with face and horns (recognition beats spectacle); under it a
    four-legged torso, wings with zero-thickness membranes and a spiked tail.
    wing_* bones pivot at the torso for flapping; legs pivot at the top for
    walking."""
    bones = [
        {"name": "body", "pivot": [0, 13, 0], "tone": "shell", "cubes": [
            box(-8, 8, -12, 16, 11, 13),
            box(-6, 8, 1, 12, 9, 12),
            box(-1, 19, -6, 2, 3, 4, "horn"),
            box(-1, 17, 3, 2, 3, 4, "horn"),
        ]},
    ]
    for name, x, z in (("leg_fl", -8, -11), ("leg_fr", 4, -11),
                       ("leg_bl", -7, 8), ("leg_br", 3, 8)):
        bones.append({
            "name": name, "parent": "body", "tone": "shell",
            "pivot": [x + 2, 8, z + 2],
            "cubes": [box(x, 2, z, 4, 6, 4), box(x, 0, z, 4, 2, 4, "horn")],
        })
    bones.append({"name": "tail1", "parent": "body", "tone": "shell",
                  "pivot": [0, 12, 13],
                  "cubes": [box(-4, 9, 13, 8, 6, 10),
                            box(-1, 15, 15, 2, 2, 3, "horn")]})
    bones.append({"name": "tail2", "parent": "tail1", "tone": "shell",
                  "pivot": [0, 12, 23],
                  "cubes": [box(-2, 10, 23, 5, 4, 9),
                            box(-1, 14, 27, 2, 2, 3, "horn")]})
    # Wings spread and raised: without the tilt a zero-thickness membrane is
    # visible only from above, and head-on the wing read as a stick. The
    # rotation sign was checked on a render, the tips point up.
    for side, sign in (("wing_left", 1), ("wing_right", -1)):
        x = 8 if sign > 0 else -22
        bones.append({
            "name": side, "parent": "body", "tone": "shell",
            "pivot": [sign * 8, 17, -4],
            "rotation": [0, 0, 28 * sign],
            "cubes": [box(x, 16, -6, 14, 2, 3),
                      box(x, 16, -3, 14, 0, 13, "wing")],
        })
    # The neck in the head's tone, not the torso's: dark on dark it vanished
    # visually, and the head "hung in the air" on the profile render.
    bones.append({"name": "neck", "parent": "body", "tone": "body",
                  "pivot": [0, 14, -12],
                  "cubes": [box(-3, 12, -19, 6, 12, 8)]})
    head_cubes = build_ball(DRAGON_HEAD_LIFT)
    for cube in head_cubes:
        cube["origin"][2] += DRAGON_HEAD_ZOFF
    bones.append({"name": "head", "parent": "neck", "tone": "body",
                  "pivot": [0, DRAGON_HEAD_LIFT + DIAMETER / 2, DRAGON_HEAD_ZOFF],
                  "cubes": head_cubes})
    horns = []
    for sign in (1, -1):
        x = 2 if sign > 0 else -4
        horn = box(x, DRAGON_HEAD_LIFT + 10, DRAGON_HEAD_ZOFF - 1, 2, 4, 2)
        horn["pivot"] = [sign * 3, DRAGON_HEAD_LIFT + 10, DRAGON_HEAD_ZOFF]
        horn["rotation"] = [0, 0, -22 * sign]
        horns.append(horn)
    bones.append({"name": "horns", "parent": "head", "tone": "horn",
                  "cubes": horns, "pivot": [0, DRAGON_HEAD_LIFT + 10, DRAGON_HEAD_ZOFF]})
    bones.append({"name": "face", "parent": "head", "tone": "body", "cubes": [],
                  "pivot": [0, DRAGON_HEAD_LIFT + DIAMETER / 2, FRONT + DRAGON_HEAD_ZOFF]})
    return bones + face_bones("face", DRAGON_HEAD_LIFT, FACE, DRAGON_HEAD_ZOFF)


def footprint(size):
    width, height, depth = size
    return 2 * (width + depth), height + depth


def faces(size, u, v):
    """Bedrock box UV layout: (x, y, width, height, tone) per face.
    A zero-thickness plane has depth = 0, and its whole unwrap collapses into
    one width x height rectangle, that is its visible side."""
    width, height, depth = size
    if depth == 0:
        return [(u, v, width, height, "side")]
    return [
        (u + depth, v, width, depth, "top"),
        (u + depth + width, v, width, depth, "bottom"),
        (u, v + depth, depth, height, "side"),
        (u + depth, v + depth, width, height, "side"),
        (u + depth + width, v + depth, depth, height, "side"),
        (u + depth + width + depth, v + depth, width, height, "side"),
    ]


class Packer:
    """Shelf packing of unwraps. Boxes of the same size share one UV, within
    one tone this breaks nothing and saves space. Every form is packed by the
    same packer: the texture is shared, and the ball is one and the same."""

    def __init__(self):
        self.shelves = []
        self.shared = {}
        self.layout = []

    def place(self, size, tone):
        key = (tuple(size), tone)
        if key in self.shared:
            return self.shared[key]
        need_w, need_h = footprint(size)
        need_w, need_h = max(1, need_w), max(1, need_h)
        for shelf in self.shelves:
            if shelf["x"] + need_w <= TEXTURE_SIZE and need_h <= shelf["h"]:
                spot = (shelf["x"], shelf["y"])
                shelf["x"] += need_w
                break
        else:
            top = self.shelves[-1]["y"] + self.shelves[-1]["h"] if self.shelves else 0
            if top + need_h > TEXTURE_SIZE:
                raise SystemExit("the unwrap does not fit a %d texture" % TEXTURE_SIZE)
            self.shelves.append({"x": need_w, "y": top, "h": need_h})
            spot = (0, top)
        self.shared[key] = spot
        self.layout.append((size, tone, spot))
        return spot


def emit(bones, packer):
    """Lays out UVs and converts the bone description into .geo.json form."""
    out = []
    for bone in bones:
        node = {"name": bone["name"]}
        if bone.get("parent"):
            node["parent"] = bone["parent"]
        node["pivot"] = bone["pivot"]
        if bone.get("rotation"):
            node["rotation"] = bone["rotation"]
        cubes = []
        for cube in bone["cubes"]:
            tone = cube.pop("tone", bone["tone"])
            cubes.append(dict(cube, uv=list(packer.place(cube["size"], tone))))
        if cubes:
            node["cubes"] = cubes
        out.append(node)
    return out


def bounds(bones):
    """Visible bounds in blocks. Too small, and the entity vanishes from the
    screen as soon as its centre leaves the frame; so a full block of margin."""
    points = [(c["origin"][i], c["origin"][i] + c["size"][i])
              for bone in bones for c in bone["cubes"] for i in (0, 1, 2)]
    axis = [points[i::3] for i in range(3)]
    extent = [max(hi for _, hi in a) - min(lo for lo, _ in a) for a in axis]
    middle = [(max(hi for _, hi in a) + min(lo for lo, _ in a)) / 2 for a in axis]
    return (round(max(extent[0], extent[2]) / 16 + 1, 2),
            round(extent[1] / 16 + 1, 2),
            [0, round(middle[1] / 16, 2), 0])


def shade(colour, factor):
    return tuple(min(255, max(0, round(channel * factor))) for channel in colour)


def render(palette, layout):
    size = TEXTURE_SIZE
    # The background is filled with the body colour, not left transparent.
    # If the UV layout drifts by a pixel from what Bedrock computes, a face
    # takes the background colour and the Friend stays visible. With a
    # transparent background the same mistake would make it invisible,
    # silently, with nothing in the log.
    pixels = [[shade(palette["body"], SHADES["side"]) + (255,)] * size for _ in range(size)]
    for cube_size, tone, (u, v) in layout:
        for x0, y0, width, height, part in faces(cube_size, u, v):
            factor = SHADES[part] if tone in SOLID else 1.0
            rgb = shade(palette[tone], factor) + (255,)
            for y in range(y0, min(y0 + height, size)):
                for x in range(x0, min(x0 + width, size)):
                    pixels[y][x] = rgb
    return pixels


def main():
    packer = Packer()
    models = []
    # The Dragon (dragon_bones) is built and rendered but left out of the
    # add-on by the author's decision of 9 September 2026: three forms plus
    # the Shade ship in the game.
    for identifier, bones in (("geometry.friend", day_bones()),
                              ("geometry.friend_night", night_bones()),
                              ("geometry.friend_shade", wraith_bones())):
        width, height, offset = bounds(bones)
        models.append({
            "description": {
                "identifier": identifier,
                "texture_width": TEXTURE_SIZE,
                "texture_height": TEXTURE_SIZE,
                "visible_bounds_width": width,
                "visible_bounds_height": height,
                "visible_bounds_offset": offset,
            },
            "bones": emit(bones, packer),
        })
        cubes = sum(len(b["cubes"]) for b in bones)
        print("%s: %d bones, %d cubes, %.2f blocks tall"
              % (identifier, len(bones), cubes, height - 1))

    (RP / "models" / "entity" / "friend.geo.json").write_text(
        json.dumps({"format_version": "1.16.0", "minecraft:geometry": models},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, palette in PALETTE.items():
        write_png(RP / "textures" / "entity" / ("%s.png" % name),
                  render(palette, packer.layout))
        print("texture: %s.png  %dx%d  body RGB%s  eyes RGB%s"
              % (name, TEXTURE_SIZE, TEXTURE_SIZE, palette["body"], palette["eye"]))


if __name__ == "__main__":
    main()
