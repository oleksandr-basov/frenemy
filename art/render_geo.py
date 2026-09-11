#!/usr/bin/env python3
"""Renders a .geo.json to PNG, look at the model without launching Minecraft.

    python3 art/render_geo.py                        the day Friend, three views
    python3 art/render_geo.py --texture friend_night
    python3 art/render_geo.py --all --clay           every geometry, shape only

Why this exists at all. The loop "fix the geometry, build, sync, boot
Windows, enter the world" takes minutes and needs a human. Without it the
model is assembled blind: that is how we got the "cubic ball" that was round
on paper. The render closes the loop in seconds and, more importantly, an
agent can use it, it sees the picture the same way a person does.

What the render catches: silhouette, proportions, UV misses (a face taking
colour from the wrong place), lost and inside-out bones. What it does not:
everything that lives in the game rather than the model, animations,
part_visibility, lighting, scale from the `minecraft:scale` component.

The projection is orthographic, no perspective, like Blockbench itself.
Mirroring of the top and bottom faces is not verified against the engine:
irrelevant for shape and colour, relevant for a texture with writing on top.
"""
import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import png

ROOT = pathlib.Path(__file__).resolve().parent.parent
RP = ROOT / "bedrock" / "resource_pack"

BACKGROUND = (58, 63, 74, 255)   # a grey between the white ball and the dark monster
SEPARATOR = (34, 37, 44, 255)
CLAY = (208, 206, 200)
LIGHT = (-0.35, 0.78, -0.52)     # from above, front and left, like Blockbench
SUPERSAMPLE = 2                  # anti-aliasing: draw larger and average

# Views: (caption, rotation around Y, tilt). Zero looks the Friend in the
# face, because an entity's front in Bedrock is the -Z side.
VIEWS = [("front", 0, 0), ("three-quarter", 35, 18), ("side", 90, 0)]


def rotation(rx, ry, rz):
    """Rotation matrix, X-Y-Z order, like Blockbench."""
    sx, cx = math.sin(math.radians(rx)), math.cos(math.radians(rx))
    sy, cy = math.sin(math.radians(ry)), math.cos(math.radians(ry))
    sz, cz = math.sin(math.radians(rz)), math.cos(math.radians(rz))
    return (
        (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
        (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
        (-sy, cy * sx, cy * cx),
    )


def apply(matrix, point):
    return tuple(sum(matrix[i][j] * point[j] for j in range(3)) for i in range(3))


def about(matrix, pivot, point):
    shifted = [point[i] - pivot[i] for i in range(3)]
    turned = apply(matrix, shifted)
    return tuple(turned[i] + pivot[i] for i in range(3))


def box_uv(uv, size):
    """Box unwrap by Minecraft's rules: (u, v, width, height) per face."""
    u, v = uv
    w, h, d = size
    return {
        "up": (u + d, v, w, d),
        "down": (u + d + w, v, w, d),
        "east": (u, v + d, d, h),
        "north": (u + d, v + d, w, h),
        "west": (u + d + w, v + d, d, h),
        "south": (u + d + w + d, v + d, w, h),
    }


def quads(cube):
    """The six faces of a cube: name, normal, four corners and their texels.

    Corners are listed in the order of walking the texture rectangle: top
    left, top right, bottom right, bottom left. That way the texture lands
    on the face the way it is seen from outside the model.
    """
    inflate = cube.get("inflate", 0)
    ox, oy, oz = cube["origin"]
    w, h, d = cube["size"]
    x0, y0, z0 = ox - inflate, oy - inflate, oz - inflate
    x1, y1, z1 = ox + w + inflate, oy + h + inflate, oz + d + inflate

    uv = cube.get("uv", [0, 0])
    if isinstance(uv, dict):
        rects = {}
        for name, face in uv.items():
            fu, fv = face["uv"]
            fw, fh = face.get("uv_size", [0, 0])
            rects[name] = (fu, fv, fw, fh)
    else:
        rects = box_uv(uv, (w, h, d))

    corners = {
        "north": ((0, 0, -1), [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)]),
        "south": ((0, 0, 1), [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)]),
        "east": ((1, 0, 0), [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)]),
        "west": ((-1, 0, 0), [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)]),
        "up": ((0, 1, 0), [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]),
        "down": ((0, -1, 0), [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)]),
    }

    for name, (normal, points) in corners.items():
        if name not in rects:
            continue
        u, v, uw, vh = rects[name]
        texels = [(u, v), (u + uw, v), (u + uw, v + vh), (u, v + vh)]
        yield name, normal, points, texels


def hidden_bones(geometry, names):
    """A hidden bone hides its children too, otherwise the face floats in the air."""
    hidden = set(names)
    for _ in range(len(geometry["bones"])):
        for bone in geometry["bones"]:
            if bone.get("parent") in hidden:
                hidden.add(bone["name"])
    return hidden


def bake(geometry, hide=()):
    """Flattens the bones into a list of faces in model coordinates."""
    bones = {bone["name"]: bone for bone in geometry["bones"]}
    hide = hidden_bones(geometry, hide)
    faces = []
    for bone in geometry["bones"]:
        if bone["name"] in hide:
            continue
        # The rotation chain: first the cube's own rotation around its own
        # pivot, then the bone rotations from this bone up to the root.
        # Pivots in Bedrock are absolute, not relative to the parent.
        chain = []
        walker = bone
        seen = set()
        while walker is not None and walker["name"] not in seen:
            seen.add(walker["name"])
            if walker.get("rotation"):
                chain.append((rotation(*walker["rotation"]), walker.get("pivot", [0, 0, 0])))
            walker = bones.get(walker.get("parent"))

        for cube in bone.get("cubes", []):
            own = []
            if cube.get("rotation"):
                own.append((rotation(*cube["rotation"]), cube.get("pivot", cube["origin"])))
            for name, normal, points, texels in quads(cube):
                moved = []
                for point in points:
                    for matrix, pivot in own + chain:
                        point = about(matrix, pivot, point)
                    moved.append(point)
                turned = normal
                for matrix, _ in own + chain:
                    turned = apply(matrix, turned)
                faces.append((bone["name"], name, turned, moved, texels))
    return faces


def project(faces, yaw, pitch):
    camera = rotation(pitch, yaw, 0)
    out = []
    for bone, name, normal, points, texels in faces:
        seen = [apply(camera, p) for p in points]
        out.append((bone, name, apply(camera, normal), seen, texels))
    return out


def raster(faces, width, height, scale, centre, texture, clay):
    size = (width, height)
    pixels = [[BACKGROUND] * width for _ in range(height)]
    depths = [[1e9] * width for _ in range(height)]
    cx, cy, _ = centre

    def screen(point):
        return ((point[0] - cx) * scale + width / 2,
                height / 2 - (point[1] - cy) * scale,
                point[2])

    for _, _, normal, points, texels in faces:
        # Back faces are skipped: a zero-thickness plane would otherwise fight
        # itself, and the inside of the ball only gets in the way.
        if normal[2] >= -1e-6:
            continue
        if clay:
            shade = max(0.25, -sum(normal[i] * LIGHT[i] for i in range(3)))
            colour = tuple(min(255, round(c * shade)) for c in CLAY) + (255,)
        else:
            colour = None
        flat = [screen(p) for p in points]
        for a, b, c in ((0, 1, 2), (0, 2, 3)):
            triangle(pixels, depths, size,
                     (flat[a], flat[b], flat[c]),
                     (texels[a], texels[b], texels[c]), texture, colour)
    return pixels


def triangle(pixels, depths, size, points, texels, texture, colour):
    width, height = size
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = points
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-9:
        return
    left = max(0, int(math.floor(min(x0, x1, x2))))
    right = min(width - 1, int(math.ceil(max(x0, x1, x2))))
    top = max(0, int(math.floor(min(y0, y1, y2))))
    bottom = min(height - 1, int(math.ceil(max(y0, y1, y2))))
    if texture:
        texture_width, texture_height, texels_rows = texture

    for y in range(top, bottom + 1):
        py = y + 0.5
        for x in range(left, right + 1):
            px = x + 0.5
            w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
            w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
            w2 = 1.0 - w0 - w1
            if w0 < -1e-9 or w1 < -1e-9 or w2 < -1e-9:
                continue
            depth = w0 * z0 + w1 * z1 + w2 * z2
            if depth >= depths[y][x]:
                continue
            if colour:
                sampled = colour
            else:
                # An orthographic projection keeps things linear, so
                # barycentric weights are enough, no correction needed.
                u = w0 * texels[0][0] + w1 * texels[1][0] + w2 * texels[2][0]
                v = w0 * texels[0][1] + w1 * texels[1][1] + w2 * texels[2][1]
                sampled = texels_rows[min(texture_height - 1, max(0, int(v)))][
                    min(texture_width - 1, max(0, int(u)))]
                if sampled[3] == 0:
                    continue
            depths[y][x] = depth
            pixels[y][x] = sampled


def downsample(pixels, factor):
    size = len(pixels) // factor
    width = len(pixels[0]) // factor
    out = []
    for y in range(size):
        row = []
        for x in range(width):
            total = [0, 0, 0, 0]
            for dy in range(factor):
                for dx in range(factor):
                    pixel = pixels[y * factor + dy][x * factor + dx]
                    for i in range(4):
                        total[i] += pixel[i]
            row.append(tuple(value // (factor * factor) for value in total))
        out.append(row)
    return out


def render(geometry, texture, tile, clay, hide=()):
    faces = bake(geometry, hide)
    if not faces:
        raise SystemExit("the geometry has no faces at all")

    views = [(caption, project(faces, yaw, pitch)) for caption, yaw, pitch in VIEWS]

    # One scale for every view: otherwise the side view "inflates" to the size
    # of the front view and proportions cannot be compared.
    xs = [p[0] for _, view in views for _, _, _, points, _ in view for p in points]
    ys = [p[1] for _, view in views for _, _, _, points, _ in view for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    edge = tile * SUPERSAMPLE
    scale = (edge * 0.86) / span
    centre = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, 0)

    tiles = [downsample(raster(view, edge, edge, scale, centre, texture, clay),
                        SUPERSAMPLE) for _, view in views]

    sheet = []
    for y in range(tile):
        row = []
        for index, image in enumerate(tiles):
            if index:
                row.append(SEPARATOR)
            row += image[y]
        sheet.append(row)
    return sheet, faces


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geo", default=str(RP / "models" / "entity" / "friend.geo.json"))
    parser.add_argument("--texture", default="friend_day",
                        help="file name in textures/entity without .png, or a path")
    parser.add_argument("--identifier", help="which geometry of the file to draw")
    parser.add_argument("--all", action="store_true", help="draw every geometry in the file")
    parser.add_argument("--hide", default="",
                        help="comma-separated bones not to draw: the geometry holds "
                             "several face expressions, shown one at a time")
    parser.add_argument("--clay", action="store_true",
                        help="no texture, lit, judge the shape alone")
    parser.add_argument("--tile", type=int, default=220, help="side of one view")
    parser.add_argument("--views", default="",
                        help="comma-separated views to draw; a single view of the "
                             "right size is a ready pack icon")
    parser.add_argument("--out", help="where to write; default art/preview/")
    options = parser.parse_args()

    if options.views:
        wanted = [name.strip() for name in options.views.split(",")]
        known = {caption: (caption, yaw, pitch) for caption, yaw, pitch in VIEWS}
        for name in wanted:
            if name not in known:
                raise SystemExit("no view \"%s\"; available: %s"
                                 % (name, ", ".join(known)))
        VIEWS[:] = [known[name] for name in wanted]

    document = json.load(open(options.geo, encoding="utf-8"))
    models = document["minecraft:geometry"]
    if options.identifier:
        models = [m for m in models if m["description"]["identifier"] == options.identifier]
        if not models:
            raise SystemExit("the file has no geometry %s; available: %s" % (
                options.identifier,
                ", ".join(m["description"]["identifier"] for m in document["minecraft:geometry"])))
    elif not options.all:
        models = models[:1]

    texture = None
    if not options.clay:
        path = pathlib.Path(options.texture)
        if not path.exists():
            path = RP / "textures" / "entity" / ("%s.png" % options.texture)
        texture = png.read_png(path)
        for model in models:
            description = model["description"]
            declared = (description.get("texture_width"), description.get("texture_height"))
            if declared != (texture[0], texture[1]):
                print("WARNING: the geometry declares a %sx%s texture, the file is %dx%d, "
                      "UVs will drift" % (declared + (texture[0], texture[1])))

    out = pathlib.Path(options.out) if options.out else ROOT / "art" / "preview"
    if not options.out:
        out.mkdir(exist_ok=True)

    for model in models:
        identifier = model["description"]["identifier"]
        hide = [name for name in options.hide.split(",") if name]
        known = {bone["name"] for bone in model["bones"]}
        for name in hide:
            if name not in known:
                raise SystemExit("nothing to hide: bone \"%s\" is not in %s; available: %s"
                                 % (name, identifier, ", ".join(sorted(known))))
        sheet, faces = render(model, texture, options.tile, options.clay, hide)
        name = identifier.replace("geometry.", "")
        suffix = "clay" if options.clay else pathlib.Path(options.texture).stem
        stem = suffix if suffix.startswith(name) else "%s_%s" % (name, suffix)
        path = pathlib.Path(options.out) if options.out else out / ("%s.png" % stem)
        png.write_png(path, sheet)

        points = [p for _, _, _, corners, _ in faces for p in corners]
        extent = [max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)]
        cubes = sum(len(b.get("cubes", [])) for b in model["bones"])
        print("%s: %d bones, %d cubes, extent %.4gx%.4gx%.4g px "
              "(%.2fx%.2fx%.2f blocks)"
              % ((identifier, len(model["bones"]), cubes) + tuple(extent)
                 + tuple(e / 16 for e in extent)))
        print("  %s, views: %s" % (path, ", ".join(caption for caption, _, _ in VIEWS)))


if __name__ == "__main__":
    main()
