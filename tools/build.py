#!/usr/bin/env python3
"""Build the Reef theme.

Generates (stdlib only, deterministic):
  * a seamless caustic light tile (PNG, embedded),
  * the animated underwater backgrounds (SVG, embedded as data URIs),
  * themes/reef.yaml with the themes "Reef", "Reef Coral" and "Reef Abyss".

Preview copies of the backgrounds are written to assets/.

    python3 tools/build.py
"""

from __future__ import annotations

import base64
import colorsys
import math
import random
import struct
import zlib
from pathlib import Path

sys_path = str(Path(__file__).resolve().parent)
import sys  # noqa: E402

if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
import reef_art as art  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
THEME_FILE = ROOT / "themes" / "reef.yaml"
ASSETS = ROOT / "assets"

VIEW_W, VIEW_H = 1600, 1000


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def f(v: float) -> str:
    """Compact number formatting for SVG."""
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in (r, g, b)))


def rgba(h: str, a: float) -> str:
    r, g, b = hex_to_rgb(h)
    return f"rgba({r}, {g}, {b}, {a:g})"


def palette(base: str, lightness: list[float]) -> dict[str, str]:
    """Eleven-step tonal palette (05 … 95) in the hue of `base`."""
    r, g, b = (c / 255 for c in hex_to_rgb(base))
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    steps = ["05", "10", "20", "30", "40", "50", "60", "70", "80", "90", "95"]
    out = {}
    for step, light in zip(steps, lightness):
        # Slightly desaturate the extremes so they don't look neon-muddy.
        s = sat * (0.75 + 0.25 * math.sin(math.pi * light))
        rr, gg, bb = colorsys.hls_to_rgb(hue, light, s)
        out[step] = rgb_to_hex(rr * 255, gg * 255, bb * 255)
    out["40"] = base
    return out


# --------------------------------------------------------------------------
# Caustic tile: periodic Worley (F2 - F1) network with a periodic domain warp
# --------------------------------------------------------------------------


def caustic_png(size: int = 224, cells: int = 3, seed: int = 20260925) -> bytes:
    rnd = random.Random(seed)
    step = size / cells
    seeds = [
        ((i + rnd.uniform(0.18, 0.82)) * step, (j + rnd.uniform(0.18, 0.82)) * step)
        for i in range(cells)
        for j in range(cells)
    ]
    tau = math.tau
    ph = [rnd.uniform(0, tau) for _ in range(8)]
    a1, a2 = size * 0.075, size * 0.03
    base_w = size * 0.032

    rows = []
    for y in range(size):
        row = bytearray([0])  # filter: none
        for x in range(size):
            u, v_ = x / size, y / size
            # Integer frequencies keep the warp periodic over the tile.
            wx = x + a1 * math.sin(tau * v_ + ph[0]) + a2 * math.sin(tau * (2 * u + 3 * v_) + ph[1]) + a2 * 0.6 * math.sin(tau * (4 * v_ - u) + ph[4])
            wy = y + a1 * math.sin(tau * u + ph[2]) + a2 * math.sin(tau * (3 * u - 2 * v_) + ph[3]) + a2 * 0.6 * math.sin(tau * (4 * u + v_) + ph[5])
            d1 = d2 = d3 = 1e9
            for sx, sy in seeds:
                dx = abs(wx - sx) % size
                dy = abs(wy - sy) % size
                dx = min(dx, size - dx)
                dy = min(dy, size - dy)
                d = math.hypot(dx, dy)
                if d < d1:
                    d1, d2, d3 = d, d1, d2
                elif d < d2:
                    d2, d3 = d, d2
                elif d < d3:
                    d3 = d
            # Line width varies along the network, like focused light does.
            width = base_w * (0.55 + 0.9 * (0.5 + 0.5 * math.sin(tau * (u + 2 * v_) + ph[6])) * (0.6 + 0.4 * math.sin(tau * (3 * u - v_) + ph[7])))
            line = max(0.0, 1.0 - (d2 - d1) / width) ** 1.7
            knot = max(0.0, 1.0 - (d3 - d1) / (width * 2.6)) ** 2
            a = min(255, round(255 * min(1.0, 0.8 * line + 0.55 * knot)))
            row += bytes((255, a))
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 4, 0, 0, 0)  # 8-bit gray+alpha
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


# --------------------------------------------------------------------------
# Corals in the style of the appriff logo: tendrils fanning out of a trunk,
# curling S-shaped and ending in round dots.
# --------------------------------------------------------------------------


class Coral:
    """Builds one coral as flat paths (absolute coordinates relative to its base),
    grouped by stroke width to keep the SVG small."""

    def __init__(self, rnd: random.Random):
        self.rnd = rnd

    def _segment(self, ox, oy, angle, length, width, curl):
        """Segment starting at (ox, oy) heading `angle` degrees from 'up'. Returns its end."""
        a = math.radians(angle)
        ux, uy = math.sin(a), -math.cos(a)  # forward
        px, py = -uy, ux  # right
        bend = -curl * 0.1 * length
        cx, cy = ox + ux * length / 2 + px * bend, oy + uy * length / 2 + py * bend
        ex, ey = ox + ux * length, oy + uy * length
        n = lambda v: str(round(v) + 0)  # integers are plenty at this scale
        self.paths.setdefault(f"{width:.1f}", []).append(f"M{n(ox)} {n(oy)}Q{n(cx)} {n(cy)} {n(ex)} {n(ey)}")
        return ex, ey

    def _tendril(self, ox, oy, angle, length, width, steps, spec, level, curl, main):
        r = self.rnd
        ex, ey = self._segment(ox, oy, angle, length, width, curl)
        if steps > 0:
            c = -curl if level == spec["flip"] else curl
            self._tendril(ex, ey, angle + c * spec["curl"] + r.uniform(-4, 4), length * spec["shrink"], width * spec["thin"], steps - 1, spec, level + 1, c, main)
            if main and level >= 1 and r.random() < spec["branch"]:
                self._tendril(ex, ey, angle + c * r.uniform(24, 44), length * r.uniform(0.75, 0.95), width * 0.7,
                              max(1, steps - 1 - int(r.random() * 2)), spec, level + 1, c, False)
        else:
            rad = max(spec["dot_min"], width * spec["dot"]) * r.uniform(0.8, 1.3)
            self.dots.append(f'<circle cx="{round(ex)}" cy="{round(ey)}" r="{f(rad)}"/>')

    def coral(self, x, y, spec, scale=1.0, sway=None) -> str:
        r = self.rnd
        self.paths: dict[str, list[str]] = {}
        self.dots: list[str] = []
        length = spec["len"] * scale * r.uniform(0.85, 1.15)
        w = spec["width"] * scale
        trunk_angle = r.uniform(-6, 6)
        tx, ty = self._segment(0, 0, trunk_angle, length * 0.8, w * 1.35, 0)
        side = -1 if r.random() < 0.5 else 1
        lean = side * r.uniform(12, 26)
        n = spec["count"][0] + int(r.random() * (spec["count"][1] - spec["count"][0] + 1))
        for i in range(n):
            a = trunk_angle + lean + (0 if n == 1 else -spec["fan"] + 2 * spec["fan"] * (i / (n - 1))) + r.uniform(-5, 5)
            t = dict(spec, flip=2 + int(r.random() * 2))
            self._tendril(tx, ty, a, length * r.uniform(0.8, 1.1), w, spec["steps"], t, 1, -side, True)
        body = "".join(f'<path stroke-width="{sw}" d="{"".join(ds)}"/>' for sw, ds in self.paths.items())
        if spec.get("tip") and spec["tip"] != "none":
            body += f'<g fill="{spec["tip"]}" stroke="none">{"".join(self.dots)}</g>'
        anim = ""
        if sway:
            amp, dur = sway
            a0 = r.uniform(-1, 1)
            anim = (
                f'<animateTransform attributeName="transform" type="rotate" additive="sum" '
                f'values="{f(a0 - amp)};{f(a0 + amp)};{f(a0 - amp)}" dur="{f(dur * r.uniform(0.8, 1.25))}s" '
                f'calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/>'
            )
        return f'<g transform="translate({f(x)} {f(y)})" stroke="{spec["color"]}">{anim}{body}</g>'


BIG = dict(len=40, width=9, steps=6, shrink=0.92, thin=0.8, curl=13, branch=0.3, dot=2.2, dot_min=4.5, fan=30, count=(3, 4))
SMALL = dict(len=30, width=6, steps=4, shrink=0.9, thin=0.8, curl=15, branch=0.25, dot=2.2, dot_min=3.5, fan=22, count=(2, 3))


def reef_layer(rnd, xs, y, base, colors, scale_range, sway, thin=1.0) -> str:
    c = Coral(rnd)
    parts = []
    for i, x in enumerate(xs):
        col = colors[i % len(colors)]
        spec = dict(base, color=col[0], tip=col[1], width=base["width"] * thin, dot_min=base["dot_min"] * (0.6 + 0.4 * thin))
        parts.append(c.coral(x, y, spec, rnd.uniform(*scale_range), sway))
    return "".join(parts)


# --------------------------------------------------------------------------
# Background building blocks
# --------------------------------------------------------------------------


def caustics_block(png_b64: str, tile: int, opacity: float, fade_stops: str, dur: float = 30) -> str:
    """Three caustic layers drifting across each other -> shimmering interference.

    The patterns are static; the rectangles they fill are moved by exactly one
    lattice vector of their pattern per loop, so the drift is seamless. (Only
    transform and opacity animations, which every engine supports.)"""
    layers = [("c1", "", 1.0, 0, 1.0, 0.7, ".45;.85;.45", 3.1),
              ("c2", "rotate(31) scale(1.55)", 1.55, 31, 1.37, 0.6, ".7;.3;.7", 3.9),
              ("c3", "rotate(-58) scale(.82)", 0.82, -58, 0.83, 0.45, ".2;.6;.2", 2.6)]
    defs = [f'<pattern id="c1" patternUnits="userSpaceOnUse" width="{tile}" height="{tile}">'
            f'<image href="data:image/png;base64,{png_b64}" width="{tile}" height="{tile}"/></pattern>']
    rects = []
    for pid, tf, sc, rot, speed, op, flick, fdur in layers:
        if tf:
            defs.append(f'<pattern id="{pid}" href="#c1" patternTransform="{tf}"/>')
        a = math.radians(rot)
        vx, vy = tile * sc * math.cos(a), tile * sc * math.sin(a)  # one lattice vector
        m = int(tile * sc * 1.5) + 2
        rects.append(
            f'<rect x="{-m}" y="{-m}" width="{VIEW_W + 2 * m}" height="{VIEW_H + 2 * m}" fill="url(#{pid})" opacity="{op:g}">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{f(vx)} {f(vy)}" dur="{f(dur * speed)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="{flick}" dur="{fdur}s" repeatCount="indefinite"/></rect>'
        )
    return (
        f'<defs>{"".join(defs)}<linearGradient id="cf" x1="0" y1="0" x2="0" y2="1">{fade_stops}</linearGradient>'
        f'<mask id="cm" maskUnits="userSpaceOnUse" x="0" y="0" width="{VIEW_W}" height="{VIEW_H}"><rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#cf)"/></mask></defs>'
        f'<g mask="url(#cm)" opacity="{opacity:g}">'
        f'<animate attributeName="opacity" values="{opacity * 0.7:.3f};{opacity:.3f};{opacity * 0.8:.3f};{opacity:.3f};{opacity * 0.7:.3f}" dur="4.7s" repeatCount="indefinite"/>'
        + "".join(rects) + "</g>"
    )


def rays_block(color: str, strength: float) -> str:
    """Soft light shafts from the surface (gradients only, no filters)."""
    rays = [(190, 120, 7, 0), (520, 190, 9, -4), (900, 100, 6, -3), (1180, 170, 8, -2), (1440, 110, 6.5, -5), (700, 70, 5, -1)]
    out = [
        f'<defs><radialGradient id="ray" cx=".5" cy="0" r="1" gradientTransform="translate(.5 0) scale(.5 1) translate(-.5 0)">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="{strength:g}"/>'
        f'<stop offset=".55" stop-color="{color}" stop-opacity="{strength * 0.25:.3f}"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>'
    ]
    for x, w, dur, delay in rays:
        out.append(
            f'<g transform="translate({x} -60) skewX(-12)"><rect x="{-w / 2:g}" width="{w}" height="{int(VIEW_H * 0.85)}" fill="url(#ray)">'
            f'<animate attributeName="opacity" values=".15;.95;.35;.8;.15" dur="{dur}s" begin="{delay}s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" values="-40 0;30 0;-10 0;40 0;-40 0" dur="{dur * 1.6:g}s" begin="{delay}s" repeatCount="indefinite"/>'
            f"</rect></g>"
        )
    return "".join(out)


def svg_wrap(body: str, bg_stops: str, defs: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" preserveAspectRatio="xMidYMax slice">'
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">{bg_stops}</linearGradient>{defs}</defs>'
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#bg)"/>{body}</svg>'
    )


def stops(*pairs) -> str:
    out = []
    for p in pairs:
        off, col = p[0], p[1]
        op = f' stop-opacity="{p[2]:g}"' if len(p) > 2 else ""
        out.append(f'<stop offset="{off:g}" stop-color="{col}"{op}/>')
    return "".join(out)


def drifting_dots(rnd: random.Random, count: int, fill_for, y_range, r_range, dur_range, move, peak_range) -> str:
    out = []
    for _ in range(count):
        x, y = rnd.uniform(0, VIEW_W), rnd.uniform(*y_range)
        d = rnd.uniform(*dur_range)
        b = -rnd.uniform(0, d)
        peak = rnd.uniform(*peak_range)
        dx, dy = move(rnd)
        out.append(
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{rnd.uniform(*r_range):.1f}" fill="{fill_for(rnd)}" opacity="0">'
            f'<animate attributeName="opacity" values="0;{peak:.2f};{peak * 0.4:.2f};{peak:.2f};0" dur="{f(d)}s" begin="{f(b)}s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{f(dx)} {f(dy)}" dur="{f(d)}s" begin="{f(b)}s" repeatCount="indefinite"/>'
            f"</circle>"
        )
    return "".join(out)


def sand(path_y: list[float], colour: str, opacity: float = 1.0) -> str:
    """Low dune strip along the very bottom."""
    xs = [i * VIEW_W / (len(path_y) - 1) for i in range(len(path_y))]
    d = art.smooth(list(zip(xs, path_y)))
    op = f' fill-opacity="{opacity:g}"' if opacity < 1 else ""
    return f'<path d="{d}V{VIEW_H}H0Z" fill="{colour}"{op}/>'


def background_coral(png_b64: str) -> str:
    """Light: sunlit coral reef lagoon with fish, rays, jellyfish and a Spanish dancer."""
    rnd = random.Random(20260925)
    defs = [
        art.glow_gradients({"gw": "#ffffff", "gp": "#ffd3e2", "gc": "#d9fbff"}),
        art.bubble_defs("#e6ffff"),
        art.DEPTH_FILTERS,
        art.jellyfish_def("jm", rnd, dict(glow="gw", glow_op=(0.18, 0.42), bell="#ffffff", bell_op=0.32, rim="#ffffff", gonad="#f49ac1",
                                          arm="#ffe4ef", arm_op=0.45, arm_edge="#ffffff", tent="#ffffff", tent_op=0.6), 3.0),
        art.lionfish_def("lf", rnd, dict(body="#f6ebe0", body_op=0.97, stripe="#7a2a24", band_top="#4a1714", thin="#8a4a3a",
                                         shade="#2a0e0c", spine="#fbf1e6", sail="#8a2c24", sail_tip="#fff4ea", blade_in="#7a2620",
                                         blade_out="#fbeee2", mem_in="#ffffff", mem_out="#cfe9f0", mem_op=0.6, outline="#4a1714",
                                         eye="#3a1810", eye_ring="#d8a648", aura_in="#ffc4b0", aura_out="#9ff4ff", rim="#ffffff")),
        art.ray_def("ry", rnd, dict(glow="gc", glow_op=(0.06, 0.16), wing="#6a92b0", back="#2f4a63", body_op=0.92, edge="#21384c",
                                    patch="#eef8fb", spot="#eef8fb")),
        art.dancer_def("sd", rnd, dict(glow="gp", glow_op=(0.12, 0.3), mantle="#e0283f", core="#ff6b6b", body_op=0.96, frill="#fff3f0", gill="#ffffff")),
    ]
    body = [rays_block("#ffffff", 0.55)]
    body.append(caustics_block(png_b64, 224, 0.72, stops((0, "#fff", 0.9), (0.5, "#fff", 0.5), (1, "#fff", 0.95))))
    body.append(drifting_dots(rnd, 28, lambda r: "#ffffff", (60, 900), (1.2, 3.2), (9, 20),
                              lambda r: (r.uniform(-90, 90), r.uniform(-60, 60)), (0.5, 0.9)))

    # Far away (small, slow, faint, blurred), behind the back reef.
    body.append(art.creature("ry", "ray", 0.12, rnd, (-320, 260), (1920, 340), 3, 160))
    body.append(art.creature("lf", "lion", 0.16, rnd, (1860, 600), (-260, 520), 4, 90))
    body.append(art.creature("jm", "jelly", 0.14, rnd, (1300, 1100), (500, -250), 4, 150))
    body.append(art.creature("sd", "dancer", 0.2, rnd, (-220, 700), (1820, 620), 4, 110))
    back = "".join([
        reef_layer(rnd, [60, 420, 760, 1120, 1480], 996, BIG, [("#8fd3dc", "#a6dde4")], (0.55, 0.7), (2.6, 8)),
        art.branching(rnd, 250, 996, 32, 2.4, 5, (12, 26), 0.84, "#9ad8e0", "#b4e4ea", (2, 7)),
        art.branching(rnd, 960, 996, 30, 2.4, 5, (12, 26), 0.84, "#9ad8e0", "#b4e4ea", (2, 7)),
        art.branching(rnd, 1300, 996, 22, 7, 4, (22, 42), 0.78, "#9ad8e0", "#b4e4ea", (1.5, 8)),
    ])
    body.append(f'<g fill="none" stroke-linecap="round" opacity=".45">{back}</g>')
    body.append(sand([990, 986, 989, 984, 988, 985, 989], "#bfe6e8", 0.7))

    # Middle distance.
    body.append(art.creature("jm", "jelly", 0.5, rnd, (280, 1180), (980, -320), 4, 170))
    body.append(art.creature("lf", "lion", 0.45, rnd, (-260, 640), (1860, 560), 5, 90))
    body.append(art.creature("sd", "dancer", 0.55, rnd, (1820, 420), (-220, 540), 4, 150))

    # Middle reef: muted colours.
    mid = "".join([
        reef_layer(rnd, [180, 540, 900, 1240, 1560], 1004, BIG,
                   [("#6fd3d1", "#93e2e0"), ("#a796e8", "#bcaff0"), ("#f3a79c", "#f8c0b8"), ("#7eaff2", "#a2c6f7")], (0.62, 0.75), (3, 7)),
        art.branching(rnd, 360, 1004, 42, 3.2, 6, (12, 26), 0.83, "#c49be6", "#e3cdf6", (2, 6), 1.8),
        art.branching(rnd, 1080, 1004, 40, 3.2, 6, (12, 26), 0.83, "#f5a98c", "#ffd8c8", (2, 6), 1.8),
        art.tube_sponge(rnd, 720, 1004, "#b9a3ef", "#7f62c4", 0.95),
        art.anemone(rnd, 1400, 1004, "#f7a8c4", "#ffe6ef", "#d9809f", 1.05),
    ])
    body.append(f'<g fill="none" stroke-linecap="round" opacity=".62">{mid}</g>')

    # Close by: big, fast and sharp.
    body.append(art.creature("lf", "lion", 0.92, rnd, (1900, 700), (-300, 760), 5, 90))
    body.append(art.creature("ry", "ray", 0.8, rnd, (-360, 200), (1960, 300), 3, 220))
    body.append(art.creature("jm", "jelly", 0.85, rnd, (1850, 800), (-250, 100), 5, 140))

    # Front reef, rooted at the very bottom.
    front = "".join([
        art.seagrass(rnd, 20, 1012, 12, "#5fc9a0", (90, 190)),
        reef_layer(rnd, [80], 1012, BIG, [("#5ce8e6", "#8ff1ef")], (1.15, 1.3), (3.5, 6)),
        art.branching(rnd, 215, 1012, 58, 5, 6, (12, 26), 0.84, "#b678e8", "#e0b8ff", (2, 6), 2.6),
        art.anemone(rnd, 330, 1012, "#ff8fb1", "#ffe0ea", "#d9577f", 1.6, 30, 6.5),
        art.tube_sponge(rnd, 445, 1012, "#ff9f6e", "#a94f2e", 1.35),
        art.brain_coral(rnd, 555, 1016, 170, 80, "#f2c46d", "#c08a3a", "#fff2c9"),
        reef_layer(rnd, [665], 1012, BIG, [("#a07af6", "#bfa6ff")], (1.15, 1.3), (3.5, 6)),
        art.branching(rnd, 780, 1012, 42, 14, 4, (22, 42), 0.78, "#ffb39e", "#ffe0d4", (1.5, 7), 6.5),
        art.seagrass(rnd, 865, 1012, 16, "#5fc9a0", (90, 200)),
        art.branching(rnd, 965, 1012, 58, 5, 6, (12, 26), 0.84, "#ff8a5c", "#ffd0b8", (2, 6), 2.6),
        art.anemone(rnd, 1070, 1012, "#7fd8f0", "#e0faff", "#4aa3bd", 1.45, 30, 6.5),
        reef_layer(rnd, [1175], 1012, BIG, [("#ff968a", "#ffb8ae")], (1.15, 1.3), (3.5, 6)),
        art.tube_sponge(rnd, 1280, 1012, "#a77ef0", "#5e3fa8", 1.3),
        art.brain_coral(rnd, 1385, 1016, 150, 70, "#c9a7f2", "#8e6ac9", "#f0e6ff"),
        art.branching(rnd, 1480, 1012, 40, 13, 4, (22, 42), 0.78, "#7fd6c0", "#d8fff4", (1.5, 7), 6),
        reef_layer(rnd, [1575], 1012, BIG, [("#60a5f8", "#95c3ff")], (1.15, 1.3), (3.5, 6)),
    ])
    body.append(f'<g fill="none" stroke-linecap="round" opacity=".88">{front}</g>')
    body.append(art.bubbles(rnd, 38, [80, 215, 330, 445, 665, 780, 965, 1070, 1175, 1280, 1480, 1575], 990, (380, 920), (2, 8), (10, 20), 0.85))
    body.append(sand([994, 989, 993, 987, 992, 988, 993, 989, 994], "#f3ead5"))
    return svg_wrap(
        "".join(body),
        stops((0, "#e4fafa"), (0.32, "#b9ecef"), (0.62, "#85d6e0"), (0.86, "#69c4d3"), (1, "#5fbccc")),
        "".join(defs),
    )


def background_abyss(png_b64: str) -> str:
    """Dark: deep sea, bioluminescent plankton, glowing animals and flora."""
    rnd = random.Random(424242)
    glow = ["#3df5e0", "#5ce8ff", "#b57cff", "#ff5fd2", "#7dffb0"]
    defs = []
    for i, c in enumerate(glow):
        defs.append(
            f'<radialGradient id="g{i}"><stop offset="0" stop-color="#ffffff" stop-opacity=".95"/>'
            f'<stop offset=".18" stop-color="{c}" stop-opacity=".85"/><stop offset=".45" stop-color="{c}" stop-opacity=".22"/>'
            f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
        )
    defs.append(
        '<radialGradient id="haze" cx=".5" cy="0" r=".9"><stop offset="0" stop-color="#1b6f9a" stop-opacity=".35"/>'
        '<stop offset="1" stop-color="#1b6f9a" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="floor" cx=".5" cy="1" r=".6" gradientTransform="translate(0 .5) scale(1 .5)">'
        '<stop offset="0" stop-color="#2a8fa0" stop-opacity=".22"/><stop offset=".5" stop-color="#5b3aa8" stop-opacity=".08"/>'
        '<stop offset="1" stop-color="#5b3aa8" stop-opacity="0"/></radialGradient>'
    )
    defs += [
        art.glow_gradients({"gc": "#3df5e0", "gv": "#b57cff", "gm": "#ff5fd2", "gb": "#5ccbff"}),
        art.bubble_defs("#7dfff0"),
        art.DEPTH_FILTERS,
        art.jellyfish_def("ja", rnd, dict(glow="gc", glow_op=(0.25, 0.65), bell="#3df5e0", bell_op=0.13, rim="#9ffaf0", gonad="#b57cff",
                                          arm="#5ce8ff", arm_op=0.22, arm_edge="#9ffaf0", tent="#7dfff0", tent_op=0.7, neon=True), 2.6),
        art.jellyfish_def("jb", rnd, dict(glow="gv", glow_op=(0.22, 0.6), bell="#b57cff", bell_op=0.14, rim="#e0c8ff", gonad="#ff5fd2",
                                          arm="#cfa8ff", arm_op=0.22, arm_edge="#e0c8ff", tent="#cfa8ff", tent_op=0.7, neon=True), 3.4),
        art.lionfish_def("lf", rnd, dict(body="#1a0c24", body_op=0.86, stripe="#ff4fae", band_top="#ff8fd8", thin="#9ef2ff",
                                         shade="#000000", spine="#bff8ff", sail="#5a1a6a", sail_tip="#ffd0f0", blade_in="#4a1460",
                                         blade_out="#ffb8ee", mem_in="#9ef2ff", mem_out="#b57cff", mem_op=0.45, outline="#ff9be4",
                                         eye="#0a3a40", eye_ring="#3df5e0", aura_in="#ff5fd2", aura_out="#6a5cff", rim="#ff9be4")),
        art.ray_def("ry", rnd, dict(glow="gb", glow_op=(0.1, 0.3), wing="#0a3a55", back="#041a2b", body_op=0.82, edge="#5ccbff",
                                    patch="#3df5e0", spot="#9ef2ff", neon=True)),
        art.dancer_def("sd", rnd, dict(glow="gm", glow_op=(0.2, 0.5), mantle="#ff2d75", core="#ff8fb1", body_op=0.78, frill="#ffd0e8",
                                       gill="#ffe6f2", neon=True)),
    ]
    body = [
        f'<rect width="{VIEW_W}" height="{VIEW_H * 0.7:g}" fill="url(#haze)"/>',
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#floor)"/>',
        rays_block("#8fe9ff", 0.12),
        caustics_block(png_b64, 260, 0.13, stops((0, "#fff", 1), (0.3, "#fff", 0.25), (0.55, "#fff", 0))),
    ]
    # Far-away bokeh.
    body.append(drifting_dots(rnd, 9, lambda r: f"url(#g{r.choice([0, 1, 2, 2, 3])})", (150, 850), (28, 64), (26, 50),
                              lambda r: (r.uniform(-30, 30), r.uniform(-30, 30)), (0.12, 0.26)))

    neon = [("#3df5e0", "#7dfff0"), ("#b57cff", "#cfa8ff"), ("#5ce8ff", "#9ef2ff"), ("#ff5fd2", "#ff9be4")]
    # Back flora, dim.
    back = "".join([
        reef_layer(rnd, [100, 480, 860, 1240, 1560], 998, BIG, neon, (0.6, 0.75), (3.5, 7), thin=0.22),
        art.branching(rnd, 300, 998, 32, 1, 5, (12, 26), 0.84, "#5ccbff", "#9ef2ff", (2, 7), 1.2),
        art.branching(rnd, 1050, 998, 30, 1, 5, (12, 26), 0.84, "#b57cff", "#e0c8ff", (2, 7), 1.2),
    ])
    body.append(f'<g fill="none" stroke-linecap="round" opacity=".3">{back}</g>')

    # Far away: faint, blurred, slow.
    body.append(art.creature("jb", "jelly", 0.15, rnd, (-260, 640), (1860, 220), 5, 150))
    body.append(art.creature("ry", "ray", 0.2, rnd, (1920, 300), (-320, 200), 3, 180))
    body.append(art.creature("lf", "lion", 0.14, rnd, (-260, 560), (1860, 640), 4, 90))
    # Middle distance.
    body.append(art.creature("ja", "jelly", 0.5, rnd, (200, 1200), (760, -320), 4, 170))
    body.append(art.creature("sd", "dancer", 0.5, rnd, (-220, 470), (1820, 380), 4, 140))

    # Middle flora.
    mid = "".join([
        reef_layer(rnd, [220, 600, 980, 1340], 1005, BIG, neon[1:] + neon[:1], (0.75, 0.9), (3.5, 7), thin=0.2),
        art.sea_pen(rnd, 420, 1005, 150, "#5ccbff", "#c2f6ff"),
        art.tube_worms(rnd, 800, 1005, "#16283a", "#ff6b9e", 4),
        art.branching(rnd, 1180, 1005, 40, 1.2, 6, (12, 26), 0.83, "#3df5e0", "#c2fff8", (2, 6), 1.4),
    ])
    body.append(f'<g fill="none" stroke-linecap="round" opacity=".55">{mid}</g>')

    # Close by.
    body.append(art.creature("ja", "jelly", 0.88, rnd, (1760, 1150), (380, -300), 4, 160))
    body.append(art.creature("lf", "lion", 0.9, rnd, (1900, 700), (-300, 760), 5, 90))
    body.append(art.creature("ry", "ray", 0.78, rnd, (-360, 260), (1960, 160), 3, 220))

    # Front flora, rooted at the very bottom.
    front = "".join([
        reef_layer(rnd, [90, 690, 1250], 1012, BIG, neon, (0.95, 1.1), (3.5, 7), thin=0.18),
        art.sea_pen(rnd, 230, 1012, 210, "#3df5e0", "#c2fff8"),
        art.tube_worms(rnd, 380, 1012, "#1c3446", "#ff5fd2"),
        art.anemone(rnd, 520, 1012, "#3df5e0", "#c2fff8", "#0d3a40", 1.0, 30, 2.0),
        art.branching(rnd, 860, 1012, 54, 1.5, 6, (12, 26), 0.84, "#b57cff", "#e0c8ff", (2, 6), 1.8),
        art.sea_pen(rnd, 1010, 1012, 180, "#ff5fd2", "#ffd0ef"),
        art.anemone(rnd, 1120, 1012, "#b57cff", "#ecdcff", "#2a1450", 0.9, 28, 2.0),
        art.tube_worms(rnd, 1400, 1012, "#1c3446", "#ff8a5c"),
        art.sea_pen(rnd, 1540, 1012, 200, "#5ccbff", "#c2f6ff"),
    ])
    body.append(
        f'<g fill="none" stroke-linecap="round" opacity=".85">{front}'
        f'<animate attributeName="opacity" values=".85;.6;.85" dur="6s" repeatCount="indefinite"/></g>'
    )
    body.append(art.bubbles(rnd, 22, [90, 230, 380, 520, 690, 860, 1010, 1120, 1250, 1400, 1540], 995, (300, 820), (1.5, 6), (12, 24), 0.6))
    body.append(sand([996, 993, 995, 992, 995, 993, 996], "#06121e"))

    # Bioluminescent plankton: drifting upwards, pulsing.
    weights = [5, 3, 2, 1, 1]
    body.append(drifting_dots(rnd, 64, lambda r: f"url(#g{r.choices(range(5), weights=weights)[0]})", (120, 1000),
                              (2.5, 15), (12, 28), lambda r: (r.uniform(-40, 40), -r.uniform(120, 380)), (0.45, 1.0)))
    return svg_wrap(
        "".join(body),
        stops((0, "#06243a"), (0.3, "#041729"), (0.65, "#020c19"), (1, "#01060e")),
        "".join(defs),
    )


def border_svg(colors: list[str], opacity: float, width: float, radius: int, dur: float = 16) -> str:
    """Hairline with an animated colour gradient, drawn as a background layer of the card.

    The SVG has no size of its own, so it fills the card and 1 user unit is 1 CSS px:
    a rounded rect with the radius of the card, stroked on its edge (half the stroke
    is clipped away, the other half is the hairline). The gradient rotates and its
    colours cycle through the palette.
    """
    n = len(colors)
    cyc = colors + [colors[0]]
    stops_ = []
    for i in range(n + 1):
        seq = [cyc[(i + k) % n] for k in range(n)] + [cyc[i % n]]
        stops_.append(
            f'<stop offset="{i / n:.3f}" stop-color="{cyc[i % n]}">'
            f'<animate attributeName="stop-color" values="{";".join(seq)}" dur="{f(dur * 0.75)}s" repeatCount="indefinite"/></stop>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"><defs>'
        '<linearGradient id="l" x1="0" y1=".5" x2="1" y2=".5">'
        f'{"".join(stops_)}'
        f'<animateTransform attributeName="gradientTransform" type="rotate" from="0 .5 .5" to="360 .5 .5" dur="{f(dur)}s" repeatCount="indefinite"/>'
        "</linearGradient></defs>"
        f'<rect width="100%" height="100%" rx="{radius}" fill="none" stroke="url(#l)" stroke-width="{width * 2:g}" stroke-opacity="{opacity:g}"/></svg>'
    )


def data_uri(svg: str) -> str:
    """Minimal URL-encoding for an SVG data URI used inside url("…")."""
    svg = svg.replace('"', "'")
    for ch, enc in (("%", "%25"), ("#", "%23"), ("<", "%3C"), (">", "%3E"), ("\n", " ")):
        svg = svg.replace(ch, enc)
    while "  " in svg:
        svg = svg.replace("  ", " ")
    return "data:image/svg+xml," + svg


# --------------------------------------------------------------------------
# Theme variables
# --------------------------------------------------------------------------

RADIUS = 13  # px, cards and badges; the gradient hairline uses the same radius

# "Avenir" first: unlike Avenir Next it has a real Light (300) that stays readable.
FONT = '"Avenir", "Avenir Next", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif'


def shared_vars() -> dict[str, str]:
    return {
        "ha-font-family-body": FONT,
        "ha-font-family-heading": FONT,
        "ha-font-weight-light": "200",
        "ha-font-weight-normal": "300",
        "ha-font-weight-body": "300",
        "ha-font-weight-medium": "400",
        "ha-font-weight-bold": "500",
        "ha-font-weight-heading": "300",
        "ha-font-weight-action": "400",
        "ha-card-header-font-size": "var(--ha-font-size-xl)",
        # Shape: soft, modern, hairlines everywhere.
        "ha-card-border-radius": f"{RADIUS}px",
        "ha-card-border-width": "0.5px",
        "ha-section-border-radius": "16px",
        "ha-dialog-border-radius": "17px",
        "ha-button-border-radius": "999px",
        "ha-badge-border-radius": f"{RADIUS}px",
        "ha-card-backdrop-filter": "blur(8px) saturate(150%)",
        "app-header-backdrop-filter": "blur(18px) saturate(160%)",
        "ha-dialog-surface-backdrop-filter": "blur(26px) saturate(170%)",
        "ha-bottom-sheet-surface-backdrop-filter": "blur(26px) saturate(170%)",
        "markdown-table-border-width": "0.5px",
        # Logo colours of the reef.
        "cyan-color": "#2fd8d5",
        "light-blue-color": "#4fb4f6",
        "blue-color": "#3d8ef2",
        "purple-color": "#a07af6",
        "deep-purple-color": "#7a5ae0",
        "pink-color": "#f06aa8",
        "teal-color": "#14b3a5",
        "deep-orange-color": "#ff7a63",
        "red-color": "#f2545b",
        "energy-water-color": "#2fd8d5",
        "energy-grid-return-color": "#a07af6",
        "energy-battery-out-color": "#3fc7b7",
        "energy-battery-in-color": "#ff8a80",
    }


def coral_vars(background: str) -> dict[str, str]:
    """Light: coral reef in shallow, sunlit water."""
    ink = "#0b3a52"
    primary = "#0b8a9c"
    accent = "#ff6f61"
    line = "#0e93a6"
    p = palette(primary, [0.07, 0.13, 0.2, 0.27, 0.33, 0.45, 0.56, 0.68, 0.8, 0.9, 0.95])
    n = palette("#3f6f7d", [0.06, 0.12, 0.2, 0.3, 0.4, 0.5, 0.6, 0.71, 0.82, 0.91, 0.96])
    v = {
        "primary-color": primary,
        "dark-primary-color": p["30"],
        "darker-primary-color": p["20"],
        "light-primary-color": p["80"],
        "accent-color": accent,
        "text-primary-color": "#ffffff",
        "text-accent-color": "#ffffff",
        "primary-text-color": ink,
        "secondary-text-color": "#3a6375",
        "disabled-text-color": "#9fb8c2",
        "disabled-color": "#8fcdd8",
        "primary-background-color": "#e8f8f9",
        "secondary-background-color": "#d4eff2",
        "clear-background-color": "#f4fcfc",
        "card-background-color": "#f6fdfd",
        "divider-color": rgba(line, 0.16),
        "outline-color": rgba(line, 0.22),
        "outline-hover-color": rgba(line, 0.45),
        "shadow-color": "rgba(8, 70, 90, 0.18)",
        "scrollbar-thumb-color": rgba(line, 0.35),
        "error-color": "#e5484d",
        "warning-color": "#f5a524",
        "success-color": "#1fae86",
        "info-color": "#2d9cdb",
        "state-icon-color": "#0f8fa1",
        # The underwater scene sits behind every panel (sidebar, dashboards, settings).
        "ha-panel-background": f'url("{background}") center bottom / cover no-repeat #85d6e0',
        "lovelace-background": "transparent",
        "ha-panel-toolbar-background": "rgba(240, 252, 252, 0.4)",
        # Glass cards with a hairline in the reef colour.
        "ha-card-background": f'url("{data_uri(border_svg(["#14bfc4", "#3d8ef2", "#8f6cf0", "#ff7a6b"], 0.85, 0.6, RADIUS))}") 0 0 / 100% 100% no-repeat border-box, linear-gradient(155deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.2) 60%, rgba(255, 255, 255, 0.32))',
        "ha-card-border-color": "transparent",
        "ha-card-box-shadow": "inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 10px 30px -14px rgba(8, 70, 90, 0.35)",
        "ha-button-box-shadow": f"inset 0 0 0 0.5px {rgba(line, 0.55)}",
        "ha-section-background-color": "rgba(255, 255, 255, 0.22)",
        "ha-color-border-normal": rgba(line, 0.42),
        # Header and sidebar.
        "app-header-background-color": "rgba(240, 252, 252, 0.42)",
        "app-header-text-color": ink,
        "app-header-border-bottom": f"0.5px solid {rgba(line, 0.38)}",
        "app-header-edit-background-color": "#0b5d6e",
        "app-header-edit-text-color": "#ffffff",
        "app-theme-color": "#c4eef1",
        "sidebar-background-color": "rgba(236, 250, 251, 0.5)",
        "sidebar-text-color": ink,
        "sidebar-icon-color": rgba(ink, 0.62),
        "sidebar-selected-text-color": primary,
        "sidebar-selected-icon-color": primary,
        # Dialogs and menus.
        "ha-dialog-surface-background": "rgba(244, 252, 252, 0.9)",
        "dialog-box-shadow": f"0 0 0 0.5px {rgba(line, 0.45)}, 0 24px 60px -18px rgba(8, 70, 90, 0.45)",
        "ha-dialog-scrim-backdrop-filter": "blur(6px) saturate(120%) brightness(92%)",
        "mdc-dialog-scrim-color": "rgba(7, 46, 71, 0.22)",
        "mdc-theme-surface": "#f6fdfd",
        # Inputs.
        "input-fill-color": "rgba(255, 255, 255, 0.55)",
        "input-disabled-fill-color": "rgba(255, 255, 255, 0.3)",
        "input-idle-line-color": rgba(line, 0.45),
        "input-hover-line-color": rgba(line, 0.9),
        "input-outlined-idle-border-color": rgba(line, 0.42),
        "input-outlined-hover-border-color": rgba(line, 0.85),
        "input-ink-color": ink,
        "input-label-ink-color": "#4d7486",
        "input-dropdown-icon-color": "#4d7486",
        "slider-track-color": rgba(line, 0.2),
        "chip-background-color": rgba(line, 0.1),
        "ha-assist-chip-filled-container-color": rgba(line, 0.1),
        "code-editor-background-color": "rgba(255, 255, 255, 0.6)",
        "markdown-code-background-color": rgba(line, 0.08),
        "table-row-background-color": "rgba(255, 255, 255, 0.35)",
        "table-row-alternative-background-color": rgba(line, 0.05),
        "data-table-background-color": "rgba(255, 255, 255, 0.0)",
        "ha-color-border-neutral-quiet": rgba(line, 0.24),
        "ha-color-border-neutral-normal": rgba(line, 0.45),
        "ha-color-border-primary-quiet": rgba(line, 0.3),
        "ha-color-text-link": p["30"],
        "markdown-link-color": p["30"],
        "ha-color-focus": accent,
        "color-1": primary,
        "color-2": accent,
        "color-3": "#7a5ae0",
        "color-4": "#3d8ef2",
        "color-5": "#f5a524",
        "color-6": "#14b3a5",
    }
    v.update({f"ha-color-primary-{k}": c for k, c in p.items()})
    v.update({f"ha-color-neutral-{k}": c for k, c in n.items()})
    return v


def abyss_vars(background: str) -> dict[str, str]:
    """Dark: deep sea, bioluminescent neon."""
    ink = "#dcf6f8"
    primary = "#3df5e0"
    accent = "#c27dff"
    line = "#3df5e0"
    p = palette(primary, [0.06, 0.11, 0.17, 0.27, 0.6, 0.66, 0.72, 0.79, 0.86, 0.92, 0.96])
    n = palette("#3b6a82", [0.04, 0.08, 0.14, 0.2, 0.3, 0.42, 0.55, 0.67, 0.79, 0.9, 0.95])
    v = {
        "primary-color": primary,
        "dark-primary-color": "#19bfae",
        "darker-primary-color": "#0f8c80",
        "light-primary-color": "#9ffaf0",
        "accent-color": accent,
        "text-primary-color": "#001a1f",
        "text-accent-color": "#12002a",
        "text-light-primary-color": "#001a1f",
        "primary-text-color": ink,
        "secondary-text-color": "#a0c6d3",
        "disabled-text-color": "#4e6b78",
        "disabled-color": "#2f7480",
        "primary-background-color": "#020a14",
        "secondary-background-color": "#071a2a",
        "clear-background-color": "#020a14",
        "card-background-color": "#071828",
        "divider-color": rgba(line, 0.12),
        "outline-color": rgba(line, 0.18),
        "outline-hover-color": rgba(line, 0.4),
        "shadow-color": "rgba(0, 0, 0, 0.6)",
        "scrollbar-thumb-color": rgba(line, 0.25),
        "error-color": "#ff4d6d",
        "warning-color": "#ffc04d",
        "success-color": "#4dffa6",
        "info-color": "#5ccbff",
        "state-icon-color": "#5ce8ff",
        "state-active-color": "#ffd166",
        "ha-panel-background": f'url("{background}") center bottom / cover no-repeat #020c19',
        "lovelace-background": "transparent",
        "ha-panel-toolbar-background": "rgba(3, 14, 26, 0.45)",
        # Glass in the abyss: dark, translucent, glowing hairline.
        "ha-card-background": f'url("{data_uri(border_svg(["#3df5e0", "#5ccbff", "#b57cff", "#ff5fd2"], 0.75, 0.6, RADIUS))}") 0 0 / 100% 100% no-repeat border-box, linear-gradient(155deg, rgba(110, 220, 255, 0.1), rgba(8, 30, 50, 0.2) 55%, rgba(6, 24, 40, 0.32))',
        "ha-card-border-color": "transparent",
        "ha-card-box-shadow": f"inset 0 1px 0 rgba(160, 255, 245, 0.07), 0 0 22px -8px {rgba(line, 0.28)}",
        "ha-button-box-shadow": f"inset 0 0 0 0.5px {rgba(line, 0.5)}, 0 0 12px -4px {rgba(line, 0.35)}",
        "ha-section-background-color": "rgba(6, 24, 40, 0.25)",
        "ha-color-border-normal": rgba(line, 0.32),
        # Header and sidebar.
        "app-header-background-color": "rgba(3, 14, 26, 0.45)",
        "app-header-text-color": ink,
        "app-header-border-bottom": f"0.5px solid {rgba(line, 0.3)}",
        "app-header-edit-background-color": "#2a1050",
        "app-header-edit-text-color": "#f0e2ff",
        "app-theme-color": "#041627",
        "sidebar-background-color": "rgba(2, 10, 20, 0.45)",
        "sidebar-text-color": ink,
        "sidebar-icon-color": rgba(ink, 0.6),
        "sidebar-selected-text-color": primary,
        "sidebar-selected-icon-color": primary,
        # Dialogs and menus.
        "ha-dialog-surface-background": "rgba(5, 20, 34, 0.9)",
        "dialog-box-shadow": f"0 0 0 0.5px {rgba(line, 0.4)}, 0 0 40px -10px {rgba(line, 0.3)}, 0 30px 70px -20px rgba(0, 0, 0, 0.8)",
        "ha-dialog-scrim-backdrop-filter": "blur(8px) brightness(60%)",
        "mdc-dialog-scrim-color": "rgba(0, 4, 10, 0.35)",
        "mdc-theme-surface": "#071828",
        # Inputs.
        "input-fill-color": "rgba(61, 245, 224, 0.05)",
        "input-disabled-fill-color": "rgba(61, 245, 224, 0.02)",
        "input-idle-line-color": rgba(line, 0.35),
        "input-hover-line-color": rgba(line, 0.85),
        "input-outlined-idle-border-color": rgba(line, 0.32),
        "input-outlined-hover-border-color": rgba(line, 0.8),
        "input-ink-color": ink,
        "input-label-ink-color": "#86aebd",
        "input-dropdown-icon-color": "#86aebd",
        "slider-track-color": rgba(line, 0.16),
        "chip-background-color": rgba(line, 0.1),
        "ha-assist-chip-filled-container-color": rgba(line, 0.1),
        "code-editor-background-color": "rgba(2, 10, 20, 0.6)",
        "markdown-code-background-color": rgba(line, 0.07),
        "table-row-background-color": "rgba(6, 24, 40, 0.35)",
        "table-row-alternative-background-color": rgba(line, 0.04),
        "data-table-background-color": "rgba(0, 0, 0, 0.0)",
        "ha-color-border-neutral-quiet": rgba(line, 0.2),
        "ha-color-border-neutral-normal": rgba(line, 0.38),
        "ha-color-border-primary-quiet": rgba(line, 0.3),
        "ha-color-on-primary-loud": "#001a1f",
        "ha-color-text-link": primary,
        "markdown-link-color": primary,
        "ha-color-focus": accent,
        "map-filter": "invert(0.9) hue-rotate(170deg) brightness(1.3) contrast(1.2) saturate(0.4)",
        "codemirror-keyword": "#c27dff",
        "codemirror-operator": "#5ce8ff",
        "codemirror-string": "#7dffb0",
        "codemirror-number": "#ff5fd2",
        "codemirror-def": "#3df5e0",
        "codemirror-comment": "#4e6b78",
        "color-1": primary,
        "color-2": accent,
        "color-3": "#ff5fd2",
        "color-4": "#5ccbff",
        "color-5": "#7dffb0",
        "color-6": "#ffd166",
    }
    v.update({f"ha-color-primary-{k}": c for k, c in p.items()})
    v.update({f"ha-color-neutral-{k}": c for k, c in n.items()})
    return v


# --------------------------------------------------------------------------
# YAML output (hand-written: every value quoted, no tags, no anchors)
# --------------------------------------------------------------------------


def q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def emit(name: str, base: dict, light: dict | None, dark: dict | None, indent="  ") -> list[str]:
    lines = [f"{name}:"]
    lines += [f"{indent}{k}: {q(v)}" for k, v in base.items()]
    if light is not None or dark is not None:
        lines.append(f"{indent}modes:")
        for mode, vars_ in (("light", light), ("dark", dark)):
            if vars_ is None:
                continue
            lines.append(f"{indent * 2}{mode}:")
            lines += [f"{indent * 3}{k}: {q(v)}" for k, v in vars_.items()]
    return lines


def main() -> None:
    png = caustic_png()
    png_b64 = base64.b64encode(png).decode()
    svg_light = background_coral(png_b64)
    svg_dark = background_abyss(png_b64)

    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "background-coral.svg").write_text(svg_light)
    (ASSETS / "background-abyss.svg").write_text(svg_dark)
    (ASSETS / "caustics.png").write_bytes(png)

    light = coral_vars(data_uri(svg_light))
    dark = abyss_vars(data_uri(svg_dark))
    shared = shared_vars()

    header = [
        "# Reef Theme for Home Assistant",
        "# https://github.com/benkrebs/reef-theme",
        "#",
        "# GENERATED FILE: edit tools/build.py and run `python3 tools/build.py`.",
        "#",
        "#   Reef        follows the light/dark setting of your profile or device",
        "#   Reef Coral  always light: a sunlit coral reef",
        "#   Reef Abyss  always dark: the deep sea, bioluminescent",
        "",
    ]
    out = header
    out += emit("Reef", shared, light, dark) + [""]
    out += emit("Reef Coral", {**shared, **light}, None, None) + [""]
    out += emit("Reef Abyss", shared, None, dark)
    THEME_FILE.parent.mkdir(exist_ok=True)
    THEME_FILE.write_text("\n".join(out) + "\n")
    print(f"caustics.png   {len(png) / 1024:6.1f} KiB")
    print(f"coral svg      {len(svg_light) / 1024:6.1f} KiB")
    print(f"abyss svg      {len(svg_dark) / 1024:6.1f} KiB")
    print(f"{THEME_FILE.relative_to(ROOT)}  {THEME_FILE.stat().st_size / 1024:6.1f} KiB")


if __name__ == "__main__":
    main()
