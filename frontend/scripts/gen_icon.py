#!/usr/bin/env python3
"""Generate PWA icons (icon-192.png, icon-512.png) with stdlib only.

Draws an indigo (#5B66DB) rounded square with a white "N", matching icon.svg.
No external deps (Pillow etc.) — uses zlib + struct to write valid RGBA PNGs.
"""
import math
import struct
import zlib
import os

BG = (0x5B, 0x66, 0xDB, 0xFF)      # #5B66DB indigo
WHITE = (0xFF, 0xFF, 0xFF, 0xFF)   # white "N"


def in_rounded(x, y, size, r):
    if r <= 0:
        return True
    if r <= x <= size - 1 - r:
        return True
    if r <= y <= size - 1 - r:
        return True
    cx = r if x < r else size - 1 - r
    cy = r if y < r else size - 1 - r
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def make_pixels(size):
    r = int(size * 0.22)
    # "N" geometry (relative to canvas)
    mx = size * 0.22
    bar_w = size * 0.12
    left_x0, left_x1 = int(mx), int(mx + bar_w)
    right_x1 = int(size - mx)
    right_x0 = int(right_x1 - bar_w)
    y0, y1 = int(size * 0.20), int(size * 0.80)
    diag_thick = size * 0.13
    half = diag_thick / 2.0

    # diagonal line: from (left_x0, y1) to (right_x1, y0)
    dx = right_x1 - left_x0
    dy = y0 - y1
    denom = math.sqrt(dx * dx + dy * dy)

    buf = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            idx = (y * size + x) * 4
            if not in_rounded(x, y, size, r):
                buf[idx:idx + 4] = bytes((0, 0, 0, 0))
                continue
            color = BG
            # left bar
            if left_x0 <= x <= left_x1 and y0 <= y <= y1:
                color = WHITE
            # right bar
            elif right_x0 <= x <= right_x1 and y0 <= y <= y1:
                color = WHITE
            else:
                # diagonal: distance from point to the line segment
                vx = x - left_x0
                vy = y - y1
                cross = abs(vx * dy - vy * dx)
                dist = cross / denom if denom > 0 else 0.0
                if dist <= half and (min(left_x0, right_x1) - 2 <= x <= max(left_x0, right_x1) + 2):
                    color = WHITE
            buf[idx:idx + 4] = bytes(color)
    return buf


def write_png(path, size):
    pixels = make_pixels(size)
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0 (None)
        raw.extend(pixels[y * size * 4:(y + 1) * size * 4])
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(ctype, data):
        return (
            struct.pack(">I", len(data))
            + ctype
            + data
            + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "public")
    out_dir = os.path.abspath(out_dir)
    write_png(os.path.join(out_dir, "icon-192.png"), 192)
    write_png(os.path.join(out_dir, "icon-512.png"), 512)
