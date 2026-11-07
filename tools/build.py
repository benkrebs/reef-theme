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


def caustics_block(png_b64: str, tile: int, opacity: float, fade_stops: str, dur: float = 46) -> str:
    """Two caustic layers drifting across each other -> shimmering interference."""
    return f"""
<defs>
 <pattern id="c1" patternUnits="userSpaceOnUse" width="{tile}" height="{tile}">
  <image href="data:image/png;base64,{png_b64}" width="{tile}" height="{tile}"/>
  <animateTransform attributeName="patternTransform" type="translate" from="0 0" to="{tile} {tile}" dur="{f(dur)}s" repeatCount="indefinite"/>
 </pattern>
 <pattern id="c2" href="#c1" patternTransform="rotate(31) scale(1.55)">
  <animateTransform attributeName="patternTransform" type="translate" additive="sum" from="0 0" to="{-tile} {tile}" dur="{f(dur * 1.37)}s" repeatCount="indefinite"/>
 </pattern>
 <linearGradient id="cf" x1="0" y1="0" x2="0" y2="1">{fade_stops}</linearGradient>
 <mask id="cm" maskUnits="userSpaceOnUse" x="0" y="0" width="{VIEW_W}" height="{VIEW_H}"><rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#cf)"/></mask>
</defs>
<g mask="url(#cm)" opacity="{opacity:g}">
 <animate attributeName="opacity" values="{opacity * 0.8:.3f};{opacity:.3f};{opacity * 0.85:.3f};{opacity * 0.8:.3f}" dur="7.3s" repeatCount="indefinite"/>
 <rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#c1)" opacity=".75"/>
 <rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#c2)" opacity=".6"/>
</g>"""


def rays_block(color: str, strength: float) -> str:
    """Soft light shafts from the surface (gradients only, no filters)."""
    rays = [(190, 120, 11, 0), (520, 190, 14, -4), (900, 100, 9, -7), (1180, 170, 13, -2), (1440, 110, 10, -5)]
    out = [
        f'<defs><radialGradient id="ray" cx=".5" cy="0" r="1" gradientTransform="translate(.5 0) scale(.5 1) translate(-.5 0)">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="{strength:g}"/>'
        f'<stop offset=".55" stop-color="{color}" stop-opacity="{strength * 0.25:.3f}"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>'
    ]
    for x, w, dur, delay in rays:
        out.append(
            f'<g transform="translate({x} -60) skewX(-12)"><rect x="{-w / 2:g}" width="{w}" height="{int(VIEW_H * 0.85)}" fill="url(#ray)">'
            f'<animate attributeName="opacity" values=".25;.9;.25" dur="{dur}s" begin="{delay}s" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" values="-24 0;24 0;-24 0" dur="{dur}s" begin="{delay}s" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/>'
            f"</rect></g>"
        )
    return "".join(out)


def svg_wrap(body: str, bg_stops: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" preserveAspectRatio="xMidYMax slice">'
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">{bg_stops}</linearGradient></defs>'
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#bg)"/>{body}</svg>'
    )


def stops(*pairs) -> str:
    out = []
    for p in pairs:
        off, col = p[0], p[1]
        op = f' stop-opacity="{p[2]:g}"' if len(p) > 2 else ""
        out.append(f'<stop offset="{off:g}" stop-color="{col}"{op}/>')
    return "".join(out)


def background_coral(png_b64: str) -> str:
    """Light: sunlit coral reef lagoon."""
    rnd = random.Random(20260925)
    body = [rays_block("#ffffff", 0.55)]
    body.append(caustics_block(png_b64, 224, 0.55, stops((0, "#fff", 0.85), (0.5, "#fff", 0.45), (1, "#fff", 0.9))))
    # Reef: back silhouettes, muted middle, colourful front, sandy floor.
    back = reef_layer(rnd, [80, 380, 700, 1020, 1330, 1560], 865, BIG, [("#7fcbd6", "#93d6df")], (0.75, 0.95), (1.2, 14))
    mid = reef_layer(rnd, [220, 540, 860, 1180, 1480], 905, BIG,
                     [("#6fd3d1", "#93e2e0"), ("#a796e8", "#bcaff0"), ("#f3a79c", "#f8c0b8"), ("#7eaff2", "#a2c6f7")], (0.62, 0.72), (1.5, 12))
    front_small = reef_layer(rnd, [300, 690, 1080, 1470], 945, SMALL,
                             [("#ff968a", "#ffb8ae"), ("#60a5f8", "#95c3ff"), ("#5ce8e6", "#8ff1ef"), ("#a07af6", "#bfa6ff")], (0.95, 1.05), (2.2, 9))
    front = reef_layer(rnd, [120, 480, 880, 1270, 1580], 945, BIG,
                       [("#5ce8e6", "#8ff1ef"), ("#a07af6", "#bfa6ff"), ("#ff968a", "#ffb8ae"), ("#60a5f8", "#95c3ff")], (0.95, 1.05), (1.8, 10))
    body.append(
        f'<g fill="none" stroke-linecap="round" opacity=".45">{back}</g>'
        f'<path fill="#a9dfe5" fill-opacity=".8" d="M0 860 C200 835 380 850 560 842 S920 820 1100 838 S1420 848 1600 832 V1000 H0Z"/>'
        f'<g fill="none" stroke-linecap="round" opacity=".6">{mid}</g>'
        f'<path fill="#e6dcc0" d="M0 905 C220 885 420 900 640 892 S1000 878 1220 895 S1480 902 1600 885 V1000 H0Z"/>'
        f'<g fill="none" stroke-linecap="round" opacity=".8">{front_small}{front}</g>'
        f'<path fill="#f3ead5" d="M0 942 C180 928 400 936 620 930 S1000 920 1220 933 S1480 938 1600 926 V1000 H0Z"/>'
    )
    return svg_wrap(
        "".join(body),
        stops((0, "#e4fafa"), (0.32, "#b9ecef"), (0.62, "#85d6e0"), (0.86, "#69c4d3"), (1, "#5fbccc")),
    )


def background_abyss(png_b64: str) -> str:
    """Dark: deep sea with bioluminescent plankton and glowing tendrils."""
    rnd = random.Random(424242)
    glow = ["#3df5e0", "#5ce8ff", "#b57cff", "#ff5fd2", "#7dffb0"]
    defs = ['<defs>']
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
        '<stop offset="1" stop-color="#5b3aa8" stop-opacity="0"/></radialGradient></defs>'
    )
    body = [
        "".join(defs),
        f'<rect width="{VIEW_W}" height="{VIEW_H * 0.7:g}" fill="url(#haze)"/>',
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#floor)"/>',
    ]
    # Faint light from far above.
    body.append(rays_block("#8fe9ff", 0.10))
    body.append(caustics_block(png_b64, 260, 0.08, stops((0, "#fff", 1), (0.3, "#fff", 0.2), (0.5, "#fff", 0))))

    # Glowing tendrils on the floor: thin neon strokes with glowing tips.
    tend = []
    neon = [("#3df5e0", "#7dfff0"), ("#b57cff", "#cfa8ff"), ("#5ce8ff", "#9ef2ff"), ("#ff5fd2", "#ff9be4")]
    for layer, (y, scale, op, thin) in enumerate([(880, (0.7, 0.9), 0.4, 0.22), (930, (0.85, 1.05), 0.8, 0.18)]):
        xs = [90, 400, 720, 1040, 1350, 1570] if layer == 0 else [210, 560, 880, 1210, 1500]
        rnd_l = random.Random(1000 + layer)
        lines = reef_layer(rnd_l, xs, y, BIG, neon[layer:] + neon[:layer], scale, (2.0, 11), thin=thin)
        tend.append(f'<g fill="none" stroke-linecap="round" opacity="{op:g}">{lines}'
                    f'<animate attributeName="opacity" values="{op:g};{op * 0.55:.3f};{op:g}" dur="{9 + layer * 4}s" repeatCount="indefinite"/></g>')
    body.append("".join(tend))

    # Bioluminescent plankton: drifting upwards, pulsing.
    parts = []
    for i in range(46):
        x = rnd.uniform(0, VIEW_W)
        y = rnd.uniform(120, VIEW_H)
        r = rnd.choice([3, 4, 5, 6, 8, 11, 15]) * rnd.uniform(0.8, 1.2)
        g = rnd.choices(range(len(glow)), weights=[5, 3, 2, 1, 1])[0]
        dur = rnd.uniform(18, 42)
        rise = rnd.uniform(80, 260)
        drift = rnd.uniform(-40, 40)
        begin = -rnd.uniform(0, dur)
        peak = rnd.uniform(0.45, 1.0)
        parts.append(
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{r:.1f}" fill="url(#g{g})" opacity="0">'
            f'<animate attributeName="opacity" values="0;{peak:.2f};{peak * 0.35:.2f};{peak:.2f};0" dur="{f(dur)}s" begin="{f(begin)}s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{f(drift)} {f(-rise)}" dur="{f(dur)}s" begin="{f(begin)}s" repeatCount="indefinite"/>'
            f"</circle>"
        )
    # A few big, soft glows far away (bokeh) for depth.
    for i in range(9):
        x, y = rnd.uniform(0, VIEW_W), rnd.uniform(150, VIEW_H * 0.85)
        r = rnd.uniform(28, 64)
        g = rnd.choice([0, 1, 2, 2, 3])
        dur = rnd.uniform(26, 50)
        peak = rnd.uniform(0.12, 0.26)
        parts.append(
            f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="url(#g{g})" opacity="0">'
            f'<animate attributeName="opacity" values="0;{peak:.2f};0" dur="{f(dur)}s" begin="{f(-rnd.uniform(0, dur))}s" repeatCount="indefinite"/></circle>'
        )
    body.append("<g>" + "".join(parts) + "</g>")
    return svg_wrap(
        "".join(body),
        stops((0, "#06243a"), (0.3, "#041729"), (0.65, "#020c19"), (1, "#01060e")),
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

FONT = '"Avenir Next", "SF Pro Display", "Segoe UI Variable Display", "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif'


def shared_vars() -> dict[str, str]:
    return {
        "ha-font-family-body": FONT,
        "ha-font-family-heading": FONT,
        "ha-font-weight-heading": "500",
        "ha-font-weight-action": "500",
        "ha-card-header-font-size": "var(--ha-font-size-xl)",
        # Shape: soft, modern, hairlines everywhere.
        "ha-card-border-radius": "20px",
        "ha-card-border-width": "0.5px",
        "ha-section-border-radius": "24px",
        "ha-dialog-border-radius": "26px",
        "ha-button-border-radius": "999px",
        "ha-badge-border-radius": "999px",
        "ha-card-backdrop-filter": "blur(14px) saturate(160%)",
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
        "secondary-text-color": "#4d7486",
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
        "lovelace-background": f'url("{background}") center bottom / cover no-repeat fixed #85d6e0',
        # Glass cards with a hairline in the reef colour.
        "ha-card-background": "rgba(255, 255, 255, 0.46)",
        "ha-card-border-color": rgba(line, 0.42),
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
        "sidebar-background-color": "#e3f6f7",
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
        "secondary-text-color": "#86aebd",
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
        "lovelace-background": f'url("{background}") center bottom / cover no-repeat fixed #020c19',
        # Glass in the abyss: dark, translucent, glowing hairline.
        "ha-card-background": "rgba(6, 24, 40, 0.42)",
        "ha-card-border-color": rgba(line, 0.32),
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
        "sidebar-background-color": "#030e1b",
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
