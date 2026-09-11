#!/usr/bin/env python3
"""PNG reading and writing with the standard library alone.

The system python3 (3.9) has no Pillow, and installing it for the project is
pointless: we only need 8-bit non-interlaced PNGs, exactly what Minecraft
understands.

The format is made of bytes, so this is the single place in the project
where bytes are touched by hand. Everything else works with a list of rows,
where each pixel is an (r, g, b, a) tuple.
"""
import struct
import zlib

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def write_png(path, pixels):
    """pixels, a list of rows, each row holding (r, g, b, a) or (r, g, b) tuples."""
    height = len(pixels)
    width = len(pixels[0])
    rows = []
    for row in pixels:
        # Filter 0 ("no filter") on every row: slightly worse compression,
        # but readable by eye in a hex dump when something goes wrong.
        rows.append(b"\x00" + b"".join(
            bytes(p if len(p) == 4 else tuple(p) + (255,)) for p in row))
    raw = b"".join(rows)

    def chunk(tag, payload):
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def read_png(path):
    """Returns (width, height, rows of (r, g, b, a) pixels)."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG" % path)

    header = None
    palette = b""
    transparency = b""
    stream = b""
    pos = 8
    while pos < len(data):
        length, tag = struct.unpack(">I4s", data[pos:pos + 8])
        payload = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif tag == b"PLTE":
            palette = payload
        elif tag == b"tRNS":
            transparency = payload
        elif tag == b"IDAT":
            stream += payload
        elif tag == b"IEND":
            break

    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or interlace or colour not in CHANNELS:
        raise ValueError("%s: only 8-bit non-interlaced PNGs are supported "
                         "(this one: depth %d, type %d, interlace %d)"
                         % (path, depth, colour, interlace))

    bpp = CHANNELS[colour]
    stride = width * bpp
    raw = zlib.decompress(stream)
    out = bytearray(stride * height)
    previous = bytearray(stride)
    pos = 0
    for y in range(height):
        method = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        # Row reconstruction per the PNG spec: each row is encoded against its
        # left neighbour, the row above, their average, or the Paeth predictor.
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            up = previous[i]
            upleft = previous[i - bpp] if i >= bpp else 0
            if method == 1:
                line[i] = (line[i] + left) & 0xFF
            elif method == 2:
                line[i] = (line[i] + up) & 0xFF
            elif method == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif method == 4:
                estimate = left + up - upleft
                da, db, dc = (abs(estimate - left), abs(estimate - up),
                              abs(estimate - upleft))
                nearest = left if (da <= db and da <= dc) else (up if db <= dc else upleft)
                line[i] = (line[i] + nearest) & 0xFF
            elif method != 0:
                raise ValueError("%s: unknown row filter %d" % (path, method))
        out[y * stride:(y + 1) * stride] = line
        previous = line

    rows = []
    for y in range(height):
        row = []
        base = y * stride
        for x in range(width):
            pixel = out[base + x * bpp:base + (x + 1) * bpp]
            if colour == 6:
                row.append(tuple(pixel))
            elif colour == 2:
                row.append(tuple(pixel) + (255,))
            elif colour == 0:
                row.append((pixel[0],) * 3 + (255,))
            elif colour == 4:
                row.append((pixel[0],) * 3 + (pixel[1],))
            else:
                index = pixel[0]
                alpha = transparency[index] if index < len(transparency) else 255
                row.append(tuple(palette[index * 3:index * 3 + 3]) + (alpha,))
        rows.append(row)
    return width, height, rows
