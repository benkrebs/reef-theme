"""Animals, corals and bubbles for the Reef backgrounds (SVG + SMIL, no filters).

Every animal is built once as a definition (<g id> inside <defs>) with its own
body animation (pulsing bell, beating fins, flapping wings, waving mantle) and a
glow that pulses with that motion. Instances <use> the definition and swim along
random, smooth paths with <animateMotion rotate="auto">.

Animals face +x in their own coordinates. A path that heads left would turn them
upside down, so such instances are mirrored vertically.
"""

from __future__ import annotations

import math
import random

TAU = math.tau

# Lite mode: no swimming, no per-frame body animation; animals and particles
# are placed as a still scene (only the caustics keep moving, see build.py).
STATIC = False


def dashes(d_lines: list[tuple], on: float, off: float, offset: float = 0.0, dot: bool = False) -> str:
    """Pre-computed dashes for straight segments: static geometry instead of a
    stroke-dasharray that the engine has to recompute on every frame."""
    out = []
    for (x1, y1), (x2, y2) in d_lines:
        L = math.hypot(x2 - x1, y2 - y1)
        if L == 0:
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        p = -offset
        while p < L:
            a, b = max(0.0, p), min(L, p + on)
            if b > a:
                if dot:
                    out.append(f"M{n(x1 + ux * a)} {n(y1 + uy * a)}h.1")
                else:
                    out.append(f"M{n(x1 + ux * a)} {n(y1 + uy * a)}L{n(x1 + ux * b)} {n(y1 + uy * b)}")
            p += on + off
    return "".join(out)
PULSE = 'calcMode="spline" keyTimes="0;.3;1" keySplines=".3 0 .2 1;.4 0 .6 1"'
EASE = 'calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"'


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def n(v: float) -> str:
    """Compact number: integers for large values, one decimal for small ones."""
    if abs(v) >= 20:
        return str(round(v))
    r = round(v, 1)
    return str(int(r)) if r == int(r) else f"{r:.1f}"


def pt(p) -> str:
    return f"{n(p[0])} {n(p[1])}"


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def smooth(pts, closed=False) -> str:
    """Smooth path through points (quadratic curves via midpoints). Fixed command
    structure for a given number of points, so it can be animated with <animate d>."""
    if closed:
        m = len(pts)
        d = f"M{pt(mid(pts[-1], pts[0]))}"
        for i in range(m):
            d += f"Q{pt(pts[i])} {pt(mid(pts[i], pts[(i + 1) % m]))}"
        return d + "Z"
    d = f"M{pt(pts[0])}"
    for i in range(1, len(pts) - 1):
        d += f"Q{pt(pts[i])} {pt(mid(pts[i], pts[i + 1]))}"
    return d + f"L{pt(pts[-1])}"


def anim_d(frames: list[str], dur: float, extra: str = "") -> str:
    vals = ";".join(frames + [frames[0]])
    return f'<animate attributeName="d" values="{vals}" dur="{n(dur)}s" repeatCount="indefinite"{extra}/>'


def anim_rot(angles: list[float], cx: float, cy: float, dur: float, begin: float = 0, extra: str = "") -> str:
    vals = ";".join(f"{n(a)} {n(cx)} {n(cy)}" for a in angles)
    b = f' begin="{n(begin)}s"' if begin else ""
    return f'<animateTransform attributeName="transform" type="rotate" additive="sum" values="{vals}" dur="{n(dur)}s"{b} repeatCount="indefinite"{extra}/>'


def anim_tr(vals: list[tuple], dur: float, extra: str = "", additive: bool = False) -> str:
    v = ";".join(f"{n(a)} {n(b)}" for a, b in vals)
    add = ' additive="sum"' if additive else ""
    return f'<animateTransform attributeName="transform" type="translate" values="{v}" dur="{n(dur)}s" repeatCount="indefinite"{add}{extra}/>'


def anim_sc(vals: list[tuple], dur: float, extra: str = "", additive: bool = True) -> str:
    v = ";".join(f"{a:g} {b:g}" for a, b in vals)
    add = ' additive="sum"' if additive else ""
    return f'<animateTransform attributeName="transform" type="scale" values="{v}" dur="{n(dur)}s" repeatCount="indefinite"{add}{extra}/>'


def osc(amp: float, phase: float, cx: float, cy: float, dur: float, bias: float = 0.0, kind: str = "rotate") -> str:
    """Sinusoidal rotation (or skewX) sampled into 13 values: a seamless, smooth
    loop that uses only transform animation, which every engine supports."""
    if kind == "rotate":
        vals = ";".join(f"{n(bias + amp * math.sin(TAU * i / 12 + phase))} {n(cx)} {n(cy)}" for i in range(13))
    else:
        vals = ";".join(n(bias + amp * math.sin(TAU * i / 12 + phase)) for i in range(13))
    return f'<animateTransform attributeName="transform" type="{kind}" additive="sum" values="{vals}" dur="{n(dur)}s" repeatCount="indefinite"/>'


def glow(grad: str, cx: float, cy: float, r: tuple, op: tuple, dur: float, extra: str = PULSE, rx_scale: float = 1.0) -> str:
    """Two-layer glow (core + halo) that swells and brightens with the motion.
    Swelling is a scale transform, brightening an opacity animation."""
    k = r[1] / r[0]
    return (
        f'<g transform="translate({n(cx)} {n(cy)}) scale({rx_scale:g} 1)">'
        f'<circle r="{n(r[1] * 1.9)}" fill="url(#{grad})" opacity="{op[0] * 0.3:.2f}">'
        f'<animate attributeName="opacity" values="{op[0] * 0.3:.2f};{op[1] * 0.45:.2f};{op[0] * 0.3:.2f}" dur="{n(dur)}s" repeatCount="indefinite" {extra}/></circle>'
        f'<g><animateTransform attributeName="transform" type="scale" values="1;{k:.2f};1" dur="{n(dur)}s" repeatCount="indefinite" {extra}/>'
        f'<circle r="{n(r[0])}" fill="url(#{grad})" opacity="{op[0]:g}">'
        f'<animate attributeName="opacity" values="{op[0]:g};{op[1]:g};{op[0]:g}" dur="{n(dur)}s" repeatCount="indefinite" {extra}/></circle></g></g>'
    )


def wander(rnd: random.Random, start, end, steps: int, amp: float):
    """Random meandering path between two points."""
    pts = [start]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    px, py = -dy / length, dx / length
    for i in range(1, steps + 1):
        t = i / (steps + 1) + rnd.uniform(-0.04, 0.04)
        o = rnd.uniform(-amp, amp)
        pts.append((start[0] + dx * t + px * o, start[1] + dy * t + py * o))
    pts.append(end)
    return pts


def swim(ref: str, path_pts, dur: float, begin: float, scale: float, opacity: float = 1.0, auto: bool = True, blur: str = "") -> str:
    """An instance of an animal swimming along a path."""
    flip = path_pts[-1][0] < path_pts[0][0] and auto
    tf = f"scale({scale:g}{' ' + format(-scale, 'g') if flip else ''})"
    op = f' opacity="{opacity:.2f}"' if opacity < 1 else ""
    fl = f' filter="url(#{blur})"' if blur else ""
    rot = ' rotate="auto"' if auto else ""
    if STATIC:
        # a still: place the animal somewhere along its path, facing its heading
        k = max(1, min(len(path_pts) - 2, int(len(path_pts) * (0.3 + 0.4 * ((begin * 7.3) % 1)))))
        (x0, y0), (x1, y1) = path_pts[k - 1], path_pts[k + 1]
        px, py = path_pts[k]
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) if auto else 0
        return f'<g{op}{fl} transform="translate({n(px)} {n(py)}) rotate({n(ang)})"><use href="#{ref}" transform="{tf}"/></g>'
    return (
        f'<g{op}{fl}><animateMotion path="{smooth(path_pts)}" dur="{n(dur)}s" begin="{n(-begin)}s" repeatCount="indefinite"{rot}/>'
        f'<use href="#{ref}" transform="{tf}"/></g>'
    )


SPECIES = {  # speed in units/s at scale 1, scale range from far (z=0) to near (z=1)
    "jelly": (26, 0.22, 0.75),
    "lion": (34, 0.24, 0.95),
    "ray": (26, 0.35, 1.1),
    "dancer": (24, 0.25, 0.85),
}

DEPTH_FILTERS = (
    '<filter id="fz1" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="1.8"/></filter>'
    '<filter id="fz2" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation=".9"/></filter>'
)


def creature(ref: str, species: str, z: float, rnd: random.Random, start, end, steps: int = 4, amp: float = 120) -> str:
    """Place an animal at depth z (0 = far, 1 = near): far ones are smaller, slower,
    fainter and blurred; near ones big, fast and sharp."""
    speed, smin, smax = SPECIES[species]
    scale = smin + (smax - smin) * z
    pts = wander(rnd, start, end, steps, amp)
    length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    dur = length / (speed * scale)
    opacity = 0.38 + 0.62 * z
    blur = ""
    return swim(ref, pts, dur, rnd.uniform(0, dur), scale, opacity, blur=blur)


def glow_gradients(colors: dict[str, str]) -> str:
    return "".join(
        f'<radialGradient id="{gid}"><stop offset="0" stop-color="{c}" stop-opacity=".9"/>'
        f'<stop offset=".35" stop-color="{c}" stop-opacity=".35"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
        for gid, c in colors.items()
    )


# --------------------------------------------------------------------------
# Jellyfish: pulsing bell, frilly oral arms, long trailing tentacles
# --------------------------------------------------------------------------


def jellyfish_def(uid: str, rnd: random.Random, s: dict, period: float) -> str:
    """Upright jelly (bell up), wrapped in rotate(90) so the bell faces +x.
    Everything moves with transform animations only: the bell contracts
    (scale), tentacles and oral arms are jointed chains that swing in a wave."""
    P = period
    bell = "M-40 0C-40-46 40-46 40 0Q30 7 20 2Q10 8 0 3Q-10 8-20 2Q-30 7-40 0Z"
    neon = s.get("neon")

    def chain(x0, y0, L, segs, amps, phase, curl, stroke, width, opacity):
        """A tentacle of `segs` segments, each swinging around its joint with a lag."""
        out, closes = [], ""
        y = y0
        seg = L / segs
        for k in range(segs):
            c = curl * (1 if k % 2 == 0 else -1)
            d = f"M{n(x0)} {n(y)}Q{n(x0 + c)} {n(y + seg / 2)} {n(x0)} {n(y + seg)}"
            strokes = ""
            if neon:
                strokes += f'<path d="{d}" stroke="{stroke}" stroke-width="{width * 4.5:g}" stroke-opacity=".12"/>'
            strokes += f'<path d="{d}" stroke="{stroke}" stroke-width="{width:g}" stroke-opacity="{opacity:g}"/>'
            out.append(f"<g>{osc(amps[k], phase - k * 0.9, x0, y, P)}{strokes}")
            closes += "</g>"
            y += seg
        return "".join(out) + closes

    tent = []
    for i in range(8):
        x0 = -34 + 68 * i / 7
        tent.append(chain(x0, 4, rnd.uniform(150, 250), 3, (4, 9, 14), rnd.uniform(0, TAU), rnd.uniform(3, 6), s["tent"], 1.1, s["tent_op"]))
    short = "".join(
        f'<path d="M{n(x)} 4Q{n(x + 2)} {n(4 + L / 2)} {n(x)} {n(4 + L)}"/>'
        for x, L in [(-38 + 76 * i / 11, rnd.uniform(22, 44)) for i in range(12)]
    )

    arms = []
    for x0, L, ph in [(-9, rnd.uniform(80, 110), 0.0), (-3, rnd.uniform(95, 125), 1.7), (3, rnd.uniform(90, 120), 3.1), (9, rnd.uniform(75, 105), 4.4)]:
        def ribbon(q0, q1):
            K = 5
            left, right = [], []
            for jq in range(K):
                q = q0 + (q1 - q0) * jq / (K - 1)
                cx = x0 + (5 + 6 * q) * math.sin(TAU * 0.8 * q + ph)
                cy = 6 + q * L
                w = 7.5 * (1 - 0.65 * q)
                ruff = 0.45 * math.sin(TAU * 3.5 * q + ph)
                left.append((cx - w * (1 + ruff), cy))
                right.append((cx + w * (1 - ruff), cy))
            return smooth(left + right[::-1], closed=True)
        jx = x0 + 8 * math.sin(TAU * 0.4 + ph)
        jy = 6 + 0.5 * L
        attrs = f'fill="{s["arm"]}" fill-opacity="{s["arm_op"]:g}" stroke="{s["arm_edge"]}" stroke-opacity=".5" stroke-width=".8"'
        arms.append(
            f'<g>{osc(7, ph, x0, 6, P)}<path d="{ribbon(0, 0.55)}" {attrs}/>'
            f'<g>{osc(12, ph - 1.1, jx, jy, P)}<path d="{ribbon(0.48, 1.0)}" {attrs}/></g></g>'
        )

    canals = "".join(f"M0-16L{n(22 * math.cos(a))} {n(-16 + 16 * math.sin(a))}" for a in [math.pi * (0.1 + 0.8 * i / 7) for i in range(8)])
    gonads = "".join(
        f'<ellipse cx="{n(7 * math.cos(a))}" cy="{n(-16 + 4 * math.sin(a))}" rx="6" ry="4" transform="rotate({n(math.degrees(a))} {n(7 * math.cos(a))} {n(-16 + 4 * math.sin(a))})"/>'
        for a in [i * TAU / 4 + 0.4 for i in range(4)]
    )
    contract = f'<animateTransform attributeName="transform" type="scale" additive="sum" values="1 1;.76 1.18;1 1" dur="{n(P)}s" repeatCount="indefinite" {PULSE}/>'
    rim = ""
    if neon:
        rim = f'<path d="{bell}" fill="none" stroke="{s["rim"]}" stroke-width="7" stroke-opacity=".14"/>'
    return (
        f'<g id="{uid}"><g transform="rotate(90)"><g>'
        + anim_tr([(0, 0), (0, -14), (0, 0)], P, " " + PULSE)
        + glow(s["glow"], 0, -18, (52, 70), (s["glow_op"][0], s["glow_op"][1]), P)
        + f'<g>{anim_sc([(1, 1), (0.8, 1.04), (1, 1)], P, " " + PULSE)}'
        f'<g fill="none" stroke-linecap="round">{"".join(tent)}</g>'
        + "".join(arms)
        + f'<g fill="none" stroke="{s["tent"]}" stroke-width=".8" stroke-opacity="{s["tent_op"] * 0.8:.2f}">{osc(9, 0, 0, 4, P, kind="skewX")}{short}</g></g>'
        f'<g>{contract}<path d="{bell}" fill="{s["bell"]}" fill-opacity="{s["bell_op"]:g}"/>{rim}'
        f'<path d="{bell}" fill="none" stroke="{s["rim"]}" stroke-width="1.2" stroke-opacity=".85"/>'
        f'<path d="{canals}" fill="none" stroke="{s["rim"]}" stroke-width=".7" stroke-opacity=".45"/>'
        f'<g fill="none" stroke="{s["gonad"]}" stroke-width="2.2" stroke-opacity=".75">{gonads}</g></g>'
        "</g></g></g>"
    )


# --------------------------------------------------------------------------
# Lionfish (Pterois volitans): banded body, huge feathery pectoral fins with
# broad membranes, long dorsal spines with flags. Fins move slowly, in waves.
# --------------------------------------------------------------------------


def lionfish_def(uid: str, rnd: random.Random, s: dict, beat: float = 6.0) -> str:
    """Lionfish after a photo: robust banded body with wavy stripes that curve
    around the eye, feather-like pectoral blades that open and close slowly like a fan,
    long banded dorsal spines with streaming sails and frayed pale tips, fringed
    tentacles on the face, and a mystic aura that breathes with the fins."""
    B = beat
    F = 10
    ts = [i / F for i in range(F)]

    body = ("M104 8C102-2 96-14 84-24C70-36 46-40 18-38C-14-36-48-24-76-10L-88-8L-88 8L-76 10"
            "C-52 22-24 30 6 32C40 34 72 30 90 22C98 18 104 14 104 8Z")

    def top(x):
        return -38 * math.sqrt(max(0.0, 1 - ((x - 18) / 106) ** 2))

    defs = [
        f'<clipPath id="{uid}c"><path d="{body}"/></clipPath>',
        f'<linearGradient id="{uid}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{s["shade"]}" stop-opacity=".5"/>'
        f'<stop offset=".45" stop-color="{s["shade"]}" stop-opacity="0"/><stop offset=".8" stop-color="#ffffff" stop-opacity=".15"/>'
        f'<stop offset="1" stop-color="#ffffff" stop-opacity=".3"/></linearGradient>',
        f'<linearGradient id="{uid}k" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{s["band_top"]}"/><stop offset="1" stop-color="{s["stripe"]}"/></linearGradient>',
        f'<radialGradient id="{uid}a"><stop offset="0" stop-color="{s["aura_in"]}" stop-opacity=".55"/>'
        f'<stop offset=".45" stop-color="{s["aura_in"]}" stop-opacity=".18"/><stop offset=".7" stop-color="{s["aura_out"]}" stop-opacity=".14"/>'
        f'<stop offset="1" stop-color="{s["aura_out"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="{uid}sl" gradientUnits="userSpaceOnUse" cx="10" cy="-30" r="125"><stop offset="0" stop-color="{s["sail"]}" stop-opacity=".92"/>'
        f'<stop offset=".72" stop-color="{s["sail"]}" stop-opacity=".8"/><stop offset=".86" stop-color="{s["sail_tip"]}" stop-opacity=".85"/>'
        f'<stop offset="1" stop-color="{s["sail_tip"]}" stop-opacity=".95"/></radialGradient>',
        f'<radialGradient id="{uid}md" gradientUnits="userSpaceOnUse" cx="-60" cy="0" r="60"><stop offset="0" stop-color="{s["mem_in"]}" stop-opacity="{s["mem_op"] * 0.5:.2f}"/>'
        f'<stop offset="1" stop-color="{s["mem_out"]}" stop-opacity="{s["mem_op"] * 0.35:.2f}"/></radialGradient>',
    ]
    PK = 'calcMode="spline" keyTimes="0;.28;1" keySplines=".2 0 .2 1;.4 0 .6 1"'

    def banded(rid, frames, width):
        defs.append(f'<path id="{rid}" d="{frames[0]}">{anim_d(frames, B)}</path>')
        return (f'<use href="#{rid}" fill="none" stroke="{s["spine"]}" stroke-width="{width:g}" stroke-linecap="round"/>'
                f'<use href="#{rid}" fill="none" stroke="{s["stripe"]}" stroke-width="{width + 0.15:g}" stroke-dasharray="9 7"/>')

    def ray_shape(cx, cy, a, L, bend):
        """A curved ray: its direction turns by `bend` towards the tip, like a
        soft fin ray flexing in the water. Returns at(f, w): point at fraction f
        of the length, offset w to the side of the next ray."""
        N = 16
        pts, dirs = [(cx, cy)], [a]
        x, y = cx, cy
        for k in range(1, N + 1):
            d = a + bend * ((k - 0.5) / N) ** 1.4
            x += math.cos(d) * L / N
            y += math.sin(d) * L / N
            pts.append((x, y))
            dirs.append(a + bend * (k / N) ** 1.4)

        def at(f, w=0.0):
            k = min(N, max(0, round(f * N)))
            (px_, py_), d = pts[k], dirs[k]
            return (px_ - math.sin(d) * w, py_ + math.cos(d) * w)

        return at

    # ---- pectoral fins: feather blades that open and close like a fan. Driven by
    # rotations (supported everywhere, cheap): each blade turns around the fin
    # base with a phase delay (a wave flows through the fan), and its outer half
    # turns around a joint, so the blade curls behind like the hem of a dress.
    def pectoral(key, cx, cy, a0, a1, rays, lmax, lmin, phase, op):
        base = [a0 + (a1 - a0) * i / (rays - 1) for i in range(rays)]
        lens = [(lmin + (lmax - lmin) * math.sin(math.pi * (0.1 + 0.85 * i / (rays - 1)))) * rnd.uniform(0.94, 1.06) for i in range(rays)]
        widths = [rnd.uniform(9, 13) for _ in range(rays)]
        amid = (a0 + a1) / 2
        gid = f"{uid}b{key}"
        defs.append(
            f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{n(cx)}" cy="{n(cy)}" r="{n(lmax)}">'
            f'<stop offset="0" stop-color="{s["blade_in"]}" stop-opacity=".95"/><stop offset=".62" stop-color="{s["blade_in"]}" stop-opacity=".82"/>'
            f'<stop offset=".82" stop-color="{s["blade_out"]}" stop-opacity=".75"/><stop offset="1" stop-color="{s["blade_out"]}" stop-opacity=".95"/></radialGradient>'
        )
        samples = [i / 12 for i in range(13)]
        out = [f'<g opacity="{op:g}" fill="url(#{gid})">']
        for i in range(rays):
            mean = amid + (base[i] - amid) * 0.9
            a = math.radians(mean)
            L, W = lens[i], widths[i]
            ux, uy = math.cos(a), math.sin(a)
            px, py = -uy, ux

            def on(f):
                return (cx + ux * f * L, cy + uy * f * L)

            def off(f, w):
                x, y = on(f)
                return (x + px * w, y + py * w)

            inner = smooth([on(0.04), on(0.32), on(0.64), off(0.64, W * 0.95), off(0.5, W * 0.9), off(0.26, W * 0.55)], closed=True)
            outer = smooth([on(0.55), on(0.8), on(1.0), off(0.97, W * 0.35), off(0.9, W * 0.95), off(0.84, W * 0.6),
                            off(0.74, W), off(0.56, W * 0.95)], closed=True)
            jx, jy = on(0.58)
            ray_in = f"M{n(cx)} {n(cy)}L{pt(on(0.6))}"
            ray_out = f"M{pt(on(0.56))}L{pt(on(1.04))}"
            rot_a, rot_b = [], []
            for t in samples:
                ph0 = TAU * (t + phase)
                phi = ph0 - 1.6 - i * 0.6
                # fan opens and closes (edges sweep most) + a wave running through it
                rot_a.append((base[i] - amid) * 0.42 * math.sin(ph0) + 13 * math.sin(phi))
                rot_b.append(28 * math.sin(phi - 1.3))
            va = ";".join(f"{n(r)} {n(cx)} {n(cy)}" for r in rot_a)
            vb = ";".join(f"{n(r)} {n(jx)} {n(jy)}" for r in rot_b)
            off0 = (i * 5.3) % 16

            def band(p1, p2, w, off=off0):
                return (f'<path d="M{pt(p1)}L{pt(p2)}" fill="none" stroke="{s["spine"]}" stroke-width="{w:g}" stroke-linecap="round"/>'
                        f'<path d="{dashes([(p1, p2)], 9, 7, off)}" fill="none" stroke="{s["stripe"]}" stroke-width="{w + 0.15:g}"/>')
            ra = "" if STATIC else f'<animateTransform attributeName="transform" type="rotate" values="{va}" dur="{n(B)}s" repeatCount="indefinite"/>'
            rb = "" if STATIC else f'<animateTransform attributeName="transform" type="rotate" values="{vb}" dur="{n(B)}s" repeatCount="indefinite"/>'
            out.append(
                f'<g>{ra}'
                f'<path d="{inner}" stroke="{s["blade_out"]}" stroke-width=".6" stroke-opacity=".4"/>{band((cx, cy), on(0.6), 1.4)}'
                f'<g>{rb}'
                f'<path d="{outer}" stroke="{s["blade_out"]}" stroke-width=".6" stroke-opacity=".5"/>{band(on(0.56), on(1.04), 1.4, off0 + 0.56 * L)}</g></g>'
            )
        out.append("</g>")
        return "".join(out)

    # ---- dorsal spines: each spine (with its flag and the sail to the next
    # spine) swings around its base; a wave runs from head to tail, the flags
    # flutter around a joint. Transform animation only.
    def dorsal():
        k = 12
        bases = [(70 - i * 10, top(70 - i * 10) + 5) for i in range(k)]
        angs = [math.radians(-100 - i * 4.6) for i in range(k)]
        lens = [(116 - i * 5.2) * rnd.uniform(0.93, 1.06) for i in range(k)]

        def P(i, f, w=0.0):
            a = angs[i]
            x, y = bases[i][0] + f * lens[i] * math.cos(a), bases[i][1] + f * lens[i] * math.sin(a)
            return (x + math.sin(a) * w, y - math.cos(a) * w)  # w > 0: trailing side

        out = []
        for i in range(k):
            W = rnd.uniform(9, 13)
            web = ""
            if i < k - 1:
                a, b = P(i, 0.8), P(i + 1, 0.76)
                m = mid(a, b)
                c1 = (a[0] + (m[0] - a[0]) * 0.6, a[1] + (m[1] - a[1]) * 0.6 + 12)
                c2 = (b[0] + (m[0] - b[0]) * 0.6, b[1] + (m[1] - b[1]) * 0.6 + 8)
                web = f'<path d="M{pt(bases[i])}L{pt(a)}C{pt(c1)} {pt(c2)} {pt(b)}L{pt(bases[i + 1])}Z" fill="url(#{uid}sl)" fill-opacity=".8"/>'
            flag = smooth([P(i, 0.62), P(i, 0.82), P(i, 1.0), P(i, 0.98, W * 0.45), P(i, 0.94, W * 0.85), P(i, 0.9, W * 0.5),
                           P(i, 0.82, W * 0.8), P(i, 0.7, W * 0.55)], closed=True)
            jx, jy = P(i, 0.62)
            spine = f"M{pt(bases[i])}L{pt(P(i, 1.0))}"
            out.append(
                f"<g>{osc(7, -i * 0.5, bases[i][0], bases[i][1], B)}{web}"
                f'<path d="{spine}" fill="none" stroke="{s["spine"]}" stroke-width="2.4" stroke-linecap="round"/>'
                f'<path d="{dashes([(bases[i], P(i, 1.0))], 9, 7, (i * 5.3) % 16)}" fill="none" stroke="{s["stripe"]}" stroke-width="2.55"/>'
                f'<g>{osc(9, -i * 0.5 - 1.2, jx, jy, B)}<path d="{flag}" fill="url(#{uid}sl)"/></g></g>'
            )
        return "".join(out)

    # ---- translucent soft fins (soft dorsal, anal, caudal) with dotted rays,
    # in two jointed halves that swing with a lag
    def soft_fin(key, cx, cy, a0, a1, rays, L, amp, speed):
        angs = [math.radians(a0 + (a1 - a0) * i / (rays - 1)) for i in range(rays)]
        inner_tips = [(cx + 0.5 * L * math.cos(a), cy + 0.5 * L * math.sin(a)) for a in angs]
        outer_tips = [(cx + L * math.cos(a), cy + L * math.sin(a)) for a in angs]
        jx, jy = mid(inner_tips[0], inner_tips[-1])
        inner = smooth([(cx, cy)] + inner_tips, closed=True)
        outer = smooth(inner_tips[::-1] + outer_tips, closed=True)
        seg_in = [((cx, cy), p) for p in inner_tips]
        seg_out = list(zip(inner_tips, outer_tips))

        def ray_paths(segs):
            d = "".join(f"M{pt(a)}L{pt(b)}" for a, b in segs)
            return (f'<path d="{d}" stroke="{s["spine"]}" stroke-width=".7" stroke-opacity=".7" fill="none"/>'
                    f'<path d="{dashes(segs, 0.1, 7, 0, dot=True)}" stroke="{s["stripe"]}" stroke-width="2.6" stroke-linecap="round" stroke-opacity=".8" fill="none"/>')
        return (f"<g>{osc(amp * 0.6, 0, cx, cy, B)}"
                f'<path d="{inner}" fill="url(#{uid}md)"/>{ray_paths(seg_in)}'
                f"<g>{osc(amp, -1.1, jx, jy, B)}"
                f'<path d="{outer}" fill="url(#{uid}md)"/>{ray_paths(seg_out)}</g></g>')

    caudal = soft_fin("c", -86, 0, 140, 220, 11, 52, 10, 1)
    soft_dorsal = soft_fin("d", -44, -30, 195, 255, 9, 46, 7, 1)
    anal = soft_fin("a", -36, 24, 110, 170, 8, 40, 7, 1)

    # ---- body stripes: wavy bands, wider on the back, thin lines in the gaps,
    # and bands radiating around the eye on the head
    bands, lines = [], []
    x0 = -82.0
    while x0 < 52:
        L, R = [], []
        for j in range(7):
            y = -44 + 82 * j / 6
            cx = x0 + 0.12 * (y + 44) * (0.4 if x0 < 0 else 0.9) + 2.2 * math.sin(y * 0.11 + x0 * 0.31)
            w = 1.6 + 2.6 * (1 - (y + 44) / 82) + 0.8 * math.sin(x0 * 0.7)
            L.append((cx - w, y))
            R.append((cx + w, y))
        bands.append(smooth(L + R[::-1], closed=True))
        lines.append(smooth([((l[0] + r[0]) / 2 + 5.2, l[1]) for l, r in zip(L, R)]))
        x0 += rnd.uniform(9, 11.5)
    ex, ey = 82, -12
    for k_, th in enumerate(range(-120, 121, 20)):
        a0 = math.radians(th)
        curl = 0.45 if th > 0 else -0.35
        L, R = [], []
        for j in range(5):
            r = 9 + 40 * j / 4
            a = a0 + curl * (r - 9) / 40
            w = 1.2 + 1.8 * j / 4
            L.append((ex + r * math.cos(a) - w * math.sin(a), ey + r * math.sin(a) + w * math.cos(a)))
            R.append((ex + r * math.cos(a) + w * math.sin(a), ey + r * math.sin(a) - w * math.cos(a)))
        bands.append(smooth(L + R[::-1], closed=True))

    body_g = (
        f'<path d="{body}" fill="{s["body"]}" fill-opacity="{s["body_op"]:g}"/>'
        f'<g clip-path="url(#{uid}c)">'
        f'<path d="{"".join(bands)}" fill="url(#{uid}k)" fill-opacity=".93"/>'
        f'<path d="{"".join(lines)}" fill="none" stroke="{s["thin"]}" stroke-width=".9" stroke-opacity=".55"/>'
        f'<path d="M74-34L92 14" stroke="{s["band_top"]}" stroke-width="6" stroke-opacity=".75"/>'
        f'<rect x="-90" y="-42" width="200" height="78" fill="url(#{uid}s)"/></g>'
        f'<path d="{body}" fill="none" stroke="{s["outline"]}" stroke-width=".9" stroke-opacity=".6"/>'
    )

    # ---- face
    def fringe(x, y, length, ang, leaves):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        stalk = f"M{n(x)} {n(y)}L{n(x + ux * length)} {n(y + uy * length)}"
        lv = "".join(
            f'<ellipse cx="{n(x + ux * length * f + (-uy) * sg * 2.2)}" cy="{n(y + uy * length * f + ux * sg * 2.2)}" rx="2.4" ry="1.3" '
            f'transform="rotate({n(ang + sg * 35)} {n(x + ux * length * f + (-uy) * sg * 2.2)} {n(y + uy * length * f + ux * sg * 2.2)})"/>'
            for f, sg in zip([0.3 + 0.7 * q / max(1, leaves - 1) for q in range(leaves)], [(-1) ** q for q in range(leaves)])
        )
        return (f'<g>{anim_rot([-7, 7, -7], x, y, rnd.uniform(2.2, 3.2), extra=" " + EASE)}'
                f'<path d="{stalk}" stroke="{s["stripe"]}" stroke-width="1.6" stroke-linecap="round"/>'
                f'<g fill="{s["stripe"]}" stroke="{s["spine"]}" stroke-width=".6" stroke-opacity=".8">{lv}</g></g>')

    face = (
        f'<circle cx="{ex}" cy="{ey}" r="7" fill="{s["eye"]}"/>'
        f'<circle cx="{ex}" cy="{ey}" r="6.2" fill="none" stroke="{s["eye_ring"]}" stroke-width="1.2" stroke-opacity=".9"/>'
        f'<circle cx="{ex + 0.6}" cy="{ey + 0.4}" r="3.8" fill="#000" opacity=".9"/>'
        f'<ellipse cx="{ex - 1.6}" cy="{ey - 1.8}" rx="1.4" ry=".9" fill="#fff" opacity=".75"/>'
        f'<path d="M{ex - 9} {ey - 3}Q{ex} {ey - 11} {ex + 9} {ey - 3}" stroke="{s["band_top"]}" stroke-width="1.6" fill="none" stroke-opacity=".7"/>'
        f'<path d="M104 8Q97 13 86 13M103 6Q96 3 89 7" stroke="{s["outline"]}" stroke-width="1.1" fill="none" stroke-opacity=".7"/>'
        f'<circle cx="96" cy="-6" r="1" fill="{s["outline"]}" opacity=".7"/>'
        f'<path d="M64-28Q53 0 62 28" stroke="{s["spine"]}" stroke-width="1.2" fill="none" stroke-opacity=".5"/>'
        + fringe(80, -20, 18, -105, 4) + fringe(86, -19, 14, -80, 3)
        + fringe(97, 15, 14, 95, 4) + fringe(88, 21, 16, 100, 5) + fringe(76, 26, 12, 105, 3)
    )

    pelvic_rays, pelvic_segs = [], []
    for i in range(4):
        a = math.radians(98 + i * 9)
        L = 60 - i * 6
        pelvic_rays.append(f"M38 26L{n(38 + L * math.cos(a))} {n(26 + L * math.sin(a))}")
        pelvic_segs.append(((38, 26), (38 + L * math.cos(a), 26 + L * math.sin(a))))
    pelvic = (
        f"<g>{anim_rot([-6, 6, -6], 38, 26, B, extra=' ' + EASE)}"
        f'<path d="M38 26L{n(38 + 56 * math.cos(math.radians(98)))} {n(26 + 56 * math.sin(math.radians(98)))}'
        f'Q26 76 {n(38 + 42 * math.cos(math.radians(125)))} {n(26 + 42 * math.sin(math.radians(125)))}Z" fill="{s["sail"]}" fill-opacity=".5"/>'
        f'<path d="{"".join(pelvic_rays)}" stroke="{s["spine"]}" stroke-width="1.4" stroke-linecap="round"/>'
        f'<path d="{dashes(pelvic_segs, 5, 5)}" stroke="{s["stripe"]}" stroke-width="1.5"/></g>'
    )

    # ---- mystic aura that breathes with the fins, a rim light and sparkles
    aura = (
        f'<g transform="translate(0 18)"><g>'
        f'<animateTransform attributeName="transform" type="scale" values="1;1.22;1" dur="{n(B)}s" repeatCount="indefinite" {PK}/>'
        f'<ellipse rx="140" ry="120" fill="url(#{uid}a)" opacity=".5">'
        f'<animate attributeName="opacity" values=".45;1;.45" dur="{n(B)}s" repeatCount="indefinite" {PK}/></ellipse></g></g>'
    )
    sparkles = "".join(
        f'<circle cx="{n(rnd.uniform(-120, 130))}" cy="{n(rnd.uniform(-120, 120))}" r="{n(rnd.uniform(1, 2.2))}" fill="{s["rim"]}" opacity="0">'
        f'<animate attributeName="opacity" values="0;.9;0" dur="{n(rnd.uniform(1.6, 3.2))}s" begin="{n(-rnd.uniform(0, 3))}s" repeatCount="indefinite"/></circle>'
        for _ in range(9)
    )
    rim = (
        f'<path d="{body}" fill="none" stroke="{s["rim"]}" stroke-width="5" stroke-opacity=".35" opacity=".3">'
        f'<animate attributeName="opacity" values=".25;1;.25" dur="{n(B)}s" repeatCount="indefinite" {PK}/></path>'
    )

    far_pec = pectoral("f", 36, 12, 120, 215, 10, 112, 62, 0.1, 0.5)
    near_pec = pectoral("n", 42, 16, 108, 208, 11, 128, 66, 0.0, 0.96)
    dors = dorsal()
    return (
        f'<g id="{uid}"><defs>{"".join(defs)}</defs><g>'
        f"{anim_tr([(0, 0), (3, -5), (0, 0)], B * 1.15, ' ' + EASE)}"
        f"{anim_rot([-1.5, 1.5, -1.5], 0, 0, B * 1.8, extra=' ' + EASE)}"
        + aura + far_pec + caudal + soft_dorsal + anal + dors + body_g + rim + face + pelvic + near_pec
        + f'<ellipse cx="45" cy="14" rx="7.5" ry="5" fill="{s["band_top"]}" opacity=".85"/>'
        + sparkles
        + "</g></g>"
    )


# --------------------------------------------------------------------------
# Eagle ray / manta (top view): slow, deep wing beats with a wave running
# out to the wing tips, a whip tail and glowing spots.
# --------------------------------------------------------------------------


def ray_def(uid: str, rnd: random.Random, s: dict, flap: float = 6.5) -> str:
    """Eagle ray / manta seen from above. The wing beat is a scale transform
    (the span narrows on the up- and downstroke), the tail a jointed chain."""
    R = flap
    tx, ty, lead = -14, 120, 0.62
    body = (f"M68-8Q74-18 60-22C42-32 12-{n(ty * lead)} {n(tx)}-{n(ty)}"
            f"C{n(tx - 12)}-{n(ty - 12)}-30-42-52-14L-62 0L-52 14"
            f"C-30 42 {n(tx - 12)} {n(ty - 12)} {n(tx)} {n(ty)}C12 {n(ty * lead)} 42 32 60 22Q74 18 68 8Z")
    tail, closes = "", ""
    x = -62
    for k in range(4):
        tail += f'<g>{osc(6 + 4 * k, -k * 0.9, x, 0, R)}<path d="M{x} 0Q{x - 17} {(-1) ** k * 3} {x - 34} 0"/>'
        closes += "</g>"
        x -= 34
    spots = "".join(f'<circle cx="{n(rnd.uniform(-40, 30))}" cy="{n(sg * rnd.uniform(14, 60))}" r="{n(rnd.uniform(1.6, 3.4))}"/>' for sg in (-1, 1) for _ in range(7))
    spots_op = f'<animate attributeName="opacity" values=".35;1;.35" dur="{n(R)}s" repeatCount="indefinite"/>' if s.get("neon") else ""
    beat = (f'<animateTransform attributeName="transform" type="scale" additive="sum" values="1 1;1.04 .78;1 1;1.02 .9;1 1" '
            f'dur="{n(R)}s" repeatCount="indefinite"/>')
    return (
        f'<g id="{uid}"><g>'
        + glow(s["glow"], 0, 0, (95, 130), s["glow_op"], R / 2, EASE, rx_scale=0.7)
        + f'<g fill="none" stroke="{s["edge"]}" stroke-width="2.4" stroke-opacity=".75" stroke-linecap="round">{tail}{closes}</g>'
        f'<defs><linearGradient id="{uid}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{s["wing"]}"/><stop offset=".5" stop-color="{s["back"]}"/><stop offset="1" stop-color="{s["wing"]}"/></linearGradient></defs>'
        f"<g>{beat}"
        f'<path d="{body}" fill="url(#{uid}g)" fill-opacity="{s["body_op"]:g}"/>'
        + (f'<path d="{body}" fill="none" stroke="{s["edge"]}" stroke-width="7" stroke-opacity=".12"/>' if s.get("neon") else "")
        + f'<path d="{body}" fill="none" stroke="{s["edge"]}" stroke-width="1.2" stroke-opacity=".85"/>'
        f'<path d="M62 0L-50 0" stroke="{s["edge"]}" stroke-width=".8" stroke-opacity=".35"/>'
        f'<ellipse cx="36" cy="-15" rx="12" ry="6" fill="{s["patch"]}" opacity=".55"/><ellipse cx="36" cy="15" rx="12" ry="6" fill="{s["patch"]}" opacity=".55"/>'
        f'<g fill="{s["spot"]}">{spots_op}{spots}</g></g>'
        "</g></g>"
    )


# --------------------------------------------------------------------------
# Spanish dancer (Hexabranchus sanguineus): swims by waving its red mantle
# --------------------------------------------------------------------------


def dancer_def(uid: str, rnd: random.Random, s: dict, wave: float = 1.7) -> str:
    """Side view of a swimming Spanish dancer. The rolling mantle is built from
    two skirts that flap (scale) in opposite phase while the body sways (skew)."""
    W = wave
    K = 12

    def edge(sign, a_scale):
        pts = []
        for jq in range(K):
            x = 60 - 120 * jq / (K - 1)
            e = math.sqrt(max(0.0, 1 - (x / 62) ** 2))
            a = 24 * (0.3 + 0.7 * (1 - abs(x) / 62)) * a_scale
            w = math.sin(TAU * x / 75 + (0 if sign < 0 else math.pi * 0.85))
            pts.append((x, sign * (9 * e + a * (0.55 + 0.45 * w))))
        return pts

    top, bot = edge(-1, 1), edge(1, 1)
    upper = smooth(top + [(x, 0) for x, _ in top[::-1]], closed=True)
    lower = smooth(bot + [(x, 0) for x, _ in bot[::-1]], closed=True)
    ruffle_t = smooth([(x, y + 3 + 1.6 * math.sin(x / 14 * TAU)) for x, y in top])
    ruffle_b = smooth([(x, y - 3 + 1.6 * math.sin(x / 14 * TAU)) for x, y in bot])
    petals = "".join(f'<ellipse cx="0" cy="-8" rx="2.8" ry="8" transform="rotate({a})"/>' for a in range(-75, 76, 25))
    spots = "".join(f'<circle cx="{n(rnd.uniform(-45, 45))}" cy="{n(rnd.uniform(-9, 9))}" r="{n(rnd.uniform(1, 2.4))}"/>' for _ in range(14))
    neon_w = (lambda d: f'<path d="{d}" fill="none" stroke="{s["frill"]}" stroke-width="8" stroke-opacity=".15"/>') if s.get("neon") else (lambda d: "")

    def skirt(d, ruffle, phase):
        flap = (f'<animateTransform attributeName="transform" type="scale" additive="sum" '
                f'values="{";".join(f"1 {0.62 + 0.38 * (0.5 + 0.5 * math.sin(TAU * i / 12 + phase)):.2f}" for i in range(13))}" '
                f'dur="{n(W)}s" repeatCount="indefinite"/>')
        return (f"<g>{flap}<path d=\"{d}\" fill=\"url(#{uid}g)\" fill-opacity=\"{s['body_op']:g}\"/>{neon_w(d)}"
                f'<path d="{d}" fill="none" stroke="{s["frill"]}" stroke-width="3.2" stroke-opacity=".95"/>'
                f'<path d="{ruffle}" fill="none" stroke="{s["frill"]}" stroke-width="1" stroke-opacity=".6"/></g>')

    return (
        f'<g id="{uid}"><g>'
        f"{anim_tr([(0, 0), (4, -3), (0, 0)], W, ' ' + EASE)}"
        + glow(s["glow"], 0, 0, (75, 100), s["glow_op"], W, EASE, rx_scale=1.3)
        + f'<defs><radialGradient id="{uid}g" r=".62"><stop offset="0" stop-color="{s["core"]}"/><stop offset=".7" stop-color="{s["mantle"]}"/>'
        f'<stop offset="1" stop-color="{s["mantle"]}" stop-opacity=".85"/></radialGradient></defs>'
        f'<g>{osc(7, 0, 0, 0, W, kind="skewX")}'
        + skirt(upper, ruffle_t, 0) + skirt(lower, ruffle_b, math.pi)
        + f'<ellipse rx="44" ry="8" fill="{s["core"]}" opacity=".6"/>'
        f'<g fill="{s["frill"]}" opacity=".35">{spots}</g>'
        f'<g transform="translate(-44 -9)" fill="{s["gill"]}" opacity=".92">{anim_sc([(1, 1), (1.25, 1.2), (1, 1)], W, " " + EASE)}{petals}</g>'
        f'<path d="M46-8Q48-21 44-26M53-7Q57-19 55-24" stroke="{s["mantle"]}" stroke-width="3.2" fill="none" stroke-linecap="round"/>'
        f'<circle cx="44" cy="-26" r="2" fill="{s["frill"]}"/><circle cx="55" cy="-24" r="2" fill="{s["frill"]}"/></g>'
        "</g></g>"
    )


# --------------------------------------------------------------------------
# Bubbles with glow
# --------------------------------------------------------------------------


def bubble_defs(glow_colour: str) -> str:
    return (
        f'<radialGradient id="bf"><stop offset=".55" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".9" stop-color="#fff" stop-opacity=".3"/><stop offset="1" stop-color="#fff" stop-opacity=".85"/></radialGradient>'
        f'<radialGradient id="bgw"><stop offset=".3" stop-color="{glow_colour}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{glow_colour}" stop-opacity="0"/></radialGradient>'
        '<g id="bub"><circle r="24" fill="url(#bgw)"/>'
        '<circle r="10" fill="url(#bf)" stroke="#fff" stroke-opacity=".95" stroke-width=".9"/>'
        '<ellipse cx="-3.6" cy="-4.2" rx="3.2" ry="1.7" transform="rotate(-38 -3.6 -4.2)" fill="#fff" opacity=".95"/>'
        '<circle cx="3.8" cy="4.4" r="1" fill="#fff" opacity=".6"/></g>'
    )


def bubbles(rnd: random.Random, count: int, sources: list[float], y0: float, rise: tuple, size: tuple, dur: tuple, opacity: float) -> str:
    out = []
    for _ in range(count):
        x = rnd.choice(sources) + rnd.uniform(-50, 50)
        y = y0 + rnd.uniform(-30, 20)
        k = rnd.uniform(*size) / 10
        d = rnd.uniform(*dur)
        h = rnd.uniform(*rise)
        w = rnd.uniform(10, 28)
        b = -rnd.uniform(0, d)
        path = ";".join(f"{n(w * math.sin(i * 1.7) * (i / 5))} {n(-h * i / 5)}" for i in range(6))
        if STATIC:
            q = rnd.uniform(0.05, 0.8)
            out.append(f'<use href="#bub" transform="translate({n(x + w * math.sin(q * 8.5) * q)} {n(y - h * q)}) scale({k:.2f})" opacity="{opacity * (1 - q) * 0.9:.2f}"/>')
            continue
        out.append(
            f'<g transform="translate({n(x)} {n(y)})" opacity="0">'
            f'<animateTransform attributeName="transform" type="translate" additive="sum" values="{path}" dur="{n(d)}s" begin="{n(b)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;{opacity:g};{opacity:g};0" keyTimes="0;.08;.8;1" dur="{n(d)}s" begin="{n(b)}s" repeatCount="indefinite"/>'
            f'<use href="#bub" transform="scale({k:.2f})"/></g>'
        )
    return "".join(out)


# --------------------------------------------------------------------------
# Flora
# --------------------------------------------------------------------------


def _sway(amp: float, dur: float, rnd: random.Random, cx: float = 0, cy: float = 0) -> str:
    a0 = rnd.uniform(-1, 1)
    return anim_rot([a0 - amp, a0 + amp, a0 - amp], cx, cy, dur * rnd.uniform(0.8, 1.2), extra=" " + EASE)


def branching(rnd: random.Random, x, y, length, width, depth, spread, shrink, colour, tip, sway, tip_r=0.0, max_dev=60) -> str:
    """Gorgonian fans (thin, deep) and staghorn corals (thick, shallow)."""
    paths: dict[str, list[str]] = {}
    tips = []

    def grow(ox, oy, ang, L, w, d):
        a = math.radians(ang)
        ex, ey = ox + L * math.sin(a), oy - L * math.cos(a)
        bend = rnd.uniform(-0.12, 0.12) * L
        cx, cy = (ox + ex) / 2 + bend * math.cos(a), (oy + ey) / 2 + bend * math.sin(a)
        paths.setdefault(f"{w:.1f}", []).append(f"M{n(ox)} {n(oy)}Q{n(cx)} {n(cy)} {n(ex)} {n(ey)}")
        if d == 0:
            tips.append((ex, ey))
            return
        for sgn in (-1, 1):
            na = ang + sgn * rnd.uniform(*spread)
            na = max(-max_dev, min(max_dev, na))
            grow(ex, ey, na, L * shrink * rnd.uniform(0.85, 1.1), max(0.6, w * 0.74), d - 1)

    grow(0, 0, rnd.uniform(-5, 5), length, width, depth)
    body = "".join(f'<path stroke-width="{sw}" d="{"".join(ds)}"/>' for sw, ds in paths.items())
    dots = ""
    if tip_r:
        dots = f'<g fill="{tip}" stroke="none">' + "".join(f'<circle cx="{n(a)}" cy="{n(b)}" r="{n(tip_r * rnd.uniform(0.8, 1.2))}"/>' for a, b in tips) + "</g>"
    return f'<g transform="translate({n(x)} {n(y)})" stroke="{colour}" fill="none" stroke-linecap="round">{_sway(sway[0], sway[1], rnd)}{body}{dots}</g>'


def tube_sponge(rnd: random.Random, x, y, colour, inner, scale=1.0) -> str:
    out = []
    for i in range(rnd.randint(3, 5)):
        dx = rnd.uniform(-26, 26) * scale
        h = rnd.uniform(70, 150) * scale
        w = rnd.uniform(14, 22) * scale
        lean = rnd.uniform(-14, 14) * scale
        tx, ty = dx + lean, -h
        out.append(
            f'<path d="M{n(dx)} 0Q{n(dx + lean * 0.2)} {n(-h / 2)} {n(tx)} {n(ty)}" stroke="{colour}" stroke-width="{n(w)}"/>'
            f'<ellipse cx="{n(tx)}" cy="{n(ty)}" rx="{n(w / 2)}" ry="{n(w / 5)}" fill="{inner}" stroke="{colour}" stroke-width="1.5"/>'
        )
    return f'<g transform="translate({n(x)} {n(y)})" fill="none">{_sway(1.5, 6, rnd)}{"".join(out)}</g>'


def anemone(rnd: random.Random, x, y, colour, tip, base, scale=1.0, count=26, width=5.0) -> str:
    groups = [[], [], []]
    tips = [[], [], []]
    for i in range(count):
        a = math.radians(-75 + 150 * i / (count - 1) + rnd.uniform(-4, 4))
        bx = 24 * scale * math.sin(a)
        by = -14 * scale
        L = rnd.uniform(38, 70) * scale * (1 - 0.25 * abs(math.sin(a)))
        curl = rnd.uniform(-0.35, 0.35)
        ex, ey = bx + L * math.sin(a + curl), by - L * math.cos(a + curl)
        cx, cy = bx + 0.55 * L * math.sin(a), by - 0.55 * L * math.cos(a)
        g = i % 3
        groups[g].append(f"M{n(bx)} {n(by)}Q{n(cx)} {n(cy)} {n(ex)} {n(ey)}")
        tips[g].append(f'<circle cx="{n(ex)}" cy="{n(ey)}" r="{n(width * 0.55)}"/>')
    out = [f'<g transform="translate({n(x)} {n(y)})">',
           f'<path d="M{n(-26 * scale)} 0C{n(-26 * scale)} {n(-22 * scale)} {n(26 * scale)} {n(-22 * scale)} {n(26 * scale)} 0Z" fill="{base}"/>']
    for g in range(3):
        out.append(
            f'<g>{anim_rot([-6, 6, -6], 0, -14 * scale, rnd.uniform(3.2, 4.8), begin=-g * 1.1, extra=" " + EASE)}'
            f'<path d="{"".join(groups[g])}" stroke="{colour}" stroke-width="{n(width)}" fill="none" stroke-linecap="round"/>'
            f'<g fill="{tip}">{"".join(tips[g])}</g></g>'
        )
    out.append("</g>")
    return "".join(out)


_uid = [0]


def brain_coral(rnd: random.Random, x, y, w, h, colour, groove, light) -> str:
    _uid[0] += 1
    cid = f"bc{_uid[0]}"
    dome = f"M{n(-w / 2)} 0C{n(-w / 2)} {n(-h * 1.33)} {n(w / 2)} {n(-h * 1.33)} {n(w / 2)} 0Z"
    lines = []
    for _ in range(int(w / 9)):
        px, py = rnd.uniform(-w / 2, w / 2), rnd.uniform(-h, -2)
        ang = rnd.uniform(0, TAU)
        pts = [(px, py)]
        for _ in range(9):
            ang += rnd.uniform(-1.1, 1.1)
            px += 7 * math.cos(ang)
            py += 7 * math.sin(ang)
            pts.append((px, py))
        lines.append(smooth(pts))
    return (
        f'<g transform="translate({n(x)} {n(y)})"><defs><clipPath id="{cid}"><path d="{dome}"/></clipPath></defs>'
        f'<path d="{dome}" fill="{colour}"/>'
        f'<path d="{"".join(lines)}" clip-path="url(#{cid})" fill="none" stroke="{groove}" stroke-width="2.2" stroke-linecap="round" stroke-opacity=".8"/>'
        f'<path d="M{n(-w * 0.32)} {n(-h * 0.75)}Q0 {n(-h * 1.05)} {n(w * 0.3)} {n(-h * 0.8)}" fill="none" stroke="{light}" stroke-width="3" stroke-opacity=".5" stroke-linecap="round"/></g>'
    )


def seagrass(rnd: random.Random, x, y, count, colour, height=(60, 140)) -> str:
    groups = [[], []]
    for i in range(count):
        bx = rnd.uniform(-30, 30)
        h = rnd.uniform(*height)
        lean = rnd.uniform(-30, 30)
        groups[i % 2].append(f"M{n(bx)} 0Q{n(bx + lean * 0.2)} {n(-h * 0.6)} {n(bx + lean)} {n(-h)}")
    out = [f'<g transform="translate({n(x)} {n(y)})" fill="none" stroke="{colour}" stroke-linecap="round">']
    for g, ds in enumerate(groups):
        out.append(f'<g>{anim_rot([-5, 5, -5], 0, 0, rnd.uniform(3.5, 5), begin=-g * 1.4, extra=" " + EASE)}<path d="{"".join(ds)}" stroke-width="3.6"/></g>')
    out.append("</g>")
    return "".join(out)


def sea_pen(rnd: random.Random, x, y, h, colour, tip) -> str:
    leaves, dots = [], []
    for i in range(16):
        q = 0.3 + 0.7 * i / 15
        sy = -h * q
        L = (22 * (1 - q) + 6) * rnd.uniform(0.9, 1.1)
        for sg in (-1, 1):
            ex, ey = sg * L, sy - L * 0.7
            leaves.append(f"M0 {n(sy)}Q{n(sg * L * 0.4)} {n(sy - L * 0.1)} {n(ex)} {n(ey)}")
            dots.append(f'<circle cx="{n(ex)}" cy="{n(ey)}" r="1.3"/>')
    return (
        f'<g transform="translate({n(x)} {n(y)})" fill="none" stroke-linecap="round">{_sway(3, 6, rnd)}'
        f'<path d="M0 0Q3 {n(-h / 2)} 0 {n(-h)}" stroke="{colour}" stroke-width="2"/>'
        f'<path d="{"".join(leaves)}" stroke="{colour}" stroke-width="1.1" stroke-opacity=".8"/>'
        f'<g fill="{tip}">{"".join(dots)}<animate attributeName="opacity" values=".3;1;.3" dur="{n(rnd.uniform(2.5, 4.5))}s" repeatCount="indefinite"/></g></g>'
    )


def tube_worms(rnd: random.Random, x, y, tube, crown, count=5) -> str:
    out = [f'<g transform="translate({n(x)} {n(y)})" fill="none" stroke-linecap="round">']
    for i in range(count):
        bx = rnd.uniform(-30, 30)
        h = rnd.uniform(50, 130)
        lean = rnd.uniform(-12, 12)
        tx, ty = bx + lean, -h
        out.append(f'<path d="M{n(bx)} 0Q{n(bx)} {n(-h / 2)} {n(tx)} {n(ty)}" stroke="{tube}" stroke-width="6"/>')
        fr = "".join(f"M0 0Q{n(9 * math.cos(math.radians(a)))} {n(-10 + 9 * math.sin(math.radians(a)) * 0.2)} {n(16 * math.cos(math.radians(a)))} {n(-16 * abs(math.sin(math.radians(a))) - 4)}" for a in range(20, 161, 14))
        d = rnd.uniform(3, 7)
        out.append(
            f'<g transform="translate({n(tx)} {n(ty)})"><g>'
            f'<animateTransform attributeName="transform" type="scale" values="1;1;.35;1" keyTimes="0;.6;.75;1" dur="{n(d)}s" begin="{n(-rnd.uniform(0, d))}s" repeatCount="indefinite"/>'
            f'<path d="{fr}" stroke="{crown}" stroke-width="1.4"/>'
            f'<path d="{fr}" stroke="{crown}" stroke-width="5" stroke-opacity=".12"/></g></g>'
        )
    out.append("</g>")
    return "".join(out)
