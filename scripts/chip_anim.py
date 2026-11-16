"""Animated ASCII chip.

Every effect is plain data (period + keyframes), so the same definition drives
  * the CSS @keyframes that ship inside the SVG, and
  * `state(...)`, which evaluates the animation at any time t for preview frames.

Effects (each one mirrors what that block really does):
  ring    gold clock pulse circulating the pad ring
  snn     neurons spike at random
  sramA/B word-line scan sweeping down each macro, alternating
  cpu     an instruction rippling through five pipeline stages
  pll     lock ripple through the concentric rings
  pmu     diagonal power-rail shimmer
"""
import html
import math
import random
from collections import defaultdict

GOLD, LED, WHITE, MINT = "#f0c75e", "#5dff9a", "#f6fff8", "#a6f2c0"
BASE, BOP = "#d6ecdc", 0.66


def _pulse(peak, rise, fall):
    return [(0, BASE, BOP), (rise, peak, 1.0), (fall, BASE, BOP), (100, BASE, BOP)]


# name: (period seconds, keyframes[(percent, fill, fill-opacity)])
ANIMS = {
    "comet":  (6.0, [(0, GOLD, 1.0), (5, GOLD, 1.0), (34, BASE, BOP), (100, BASE, BOP)]),
    "spikeA": (2.0, _pulse(LED, 6, 26)),
    "spikeB": (3.0, _pulse(LED, 5, 20)),
    "wl":     (3.0, _pulse(WHITE, 5, 17)),
    "pipe":   (2.0, _pulse(LED, 6, 20)),
    "ripple": (3.0, _pulse(GOLD, 9, 30)),
    "shim":   (2.0, _pulse(MINT, 8, 26)),
}
RING_N = 24
PIPE_STAGES = 5


# ---- helpers ---------------------------------------------------------------
def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _mix(a, b, f):
    ra, rb = _hex(a), _hex(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(ra, rb))


def state(anim, off, t):
    """(fill, fill-opacity) of an animation at time t, given its phase offset `off`."""
    period, kf = ANIMS[anim]
    ph = (((t - off) % period) / period) * 100
    for (p0, c0, o0), (p1, c1, o1) in zip(kf, kf[1:]):
        if p0 <= ph <= p1:
            f = 0 if p1 == p0 else (ph - p0) / (p1 - p0)
            return _mix(c0, c1, f), o0 + (o1 - o0) * f
    return kf[-1][1], kf[-1][2]


def perim_t(dx, dy):
    """Position 0..1 around a square perimeter, clockwise from the top-left."""
    ax, ay = abs(dx), abs(dy)
    if ay >= ax:
        if dy < 0:
            return 0.25 * (0.5 + dx / (2 * ay))
        return 0.5 + 0.25 * (0.5 - dx / (2 * ay))
    if dx > 0:
        return 0.25 + 0.25 * (0.5 + dy / (2 * ax))
    return 0.75 + 0.25 * (0.5 - dy / (2 * ax))


def _bounds(labels):
    b = {}
    for r, row in enumerate(labels):
        for c, lab in enumerate(row):
            if lab is None:
                continue
            r0, r1, c0, c1 = b.get(lab, (r, r, c, c))
            b[lab] = (min(r0, r), max(r1, r), min(c0, c), max(c1, c))
    return b


# ---- assign every character to an animation group --------------------------
def assign(lines, labels, cw, lh):
    """Returns (cells, classes). cells = [(cls|None, row, col, char)], classes = {cls: (anim, off)}."""
    rows, cols = len(lines), len(lines[0])
    classes, cells = {}, []
    bounds = _bounds(labels) if labels else {}
    mid_x, mid_y = cols * cw / 2, rows * lh / 2

    def reg(cls, anim, off):
        classes[cls] = (anim, off)
        return cls

    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == " ":
                continue
            lab = labels[r][c] if labels else "photo"
            cls = None
            if lab == "ring":
                k = int(perim_t((c + .5) * cw - mid_x, (r + .5) * lh - mid_y) * RING_N) % RING_N
                cls = reg(f"r{k}", "comet", ANIMS["comet"][0] * k / RING_N)
            elif lab in ("snn", "photo"):
                g = random.Random(r * 1009 + c * 31).randrange(10)
                cls = reg(f"n{g}", "spikeA" if g % 2 == 0 else "spikeB", (g * 0.37) % 3.0)
            elif lab in ("sramA", "sramB"):
                r0 = bounds[lab][0]
                i = r - r0
                base = 0.0 if lab == "sramA" else 1.5
                cls = reg(f"{'a' if lab == 'sramA' else 'b'}{i}", "wl", base + i * 0.16)
            elif lab == "cpu":
                _, _, c0, c1 = bounds["cpu"]
                b = min(PIPE_STAGES - 1, int((c - c0) / (c1 - c0 + 1) * PIPE_STAGES))
                cls = reg(f"p{b}", "pipe", b * 0.22)
            elif lab == "pll":
                r0, r1, c0, c1 = bounds["pll"]
                d = min(c - c0, c1 - c, r - r0, r1 - r) // 2
                cls = reg(f"l{d}", "ripple", d * 0.3)
            elif lab == "pmu":
                k = ((c + r) // 2) % 10
                cls = reg(f"h{k}", "shim", k * 0.15)
            cells.append((cls, r, c, ch))
    return cells, classes


# ---- output ----------------------------------------------------------------
def css(classes):
    used = sorted({a for a, _ in classes.values()})
    out = []
    for a in used:
        period, kf = ANIMS[a]
        frames = "".join(f"{p}%{{fill:{c};fill-opacity:{o}}}" for p, c, o in kf)
        out.append(f"@keyframes {a}{{{frames}}}")
    for cls, (a, off) in sorted(classes.items()):
        period = ANIMS[a][0]
        delay = (period - off % period) % period
        out.append(f".{cls}{{animation:{a} {period:g}s linear infinite;"
                   f"animation-delay:-{delay:.2f}s}}")
    return "".join(out)


def emit(cells, classes, ax, ay, cw, lh, t=None):
    """<text> rows. t=None -> CSS-animated classes; t=float -> inline state for a still frame."""
    groups = defaultdict(lambda: defaultdict(list))
    for cls, r, c, ch in cells:
        groups[cls][r].append((c, ch))
    out = []
    for cls, rowd in groups.items():
        if cls is None:
            attr = ""
        elif t is None:
            attr = f' class="{cls}"'
        else:
            anim, off = classes[cls]
            fill, op = state(anim, off, t)
            attr = f' fill="{fill}" fill-opacity="{op:.3f}"'
        for r, items in sorted(rowd.items()):
            xs = " ".join(f"{ax + c * cw:.1f}" for c, _ in items)
            text = html.escape("".join(ch for _, ch in items))
            out.append(f'<text{attr} x="{xs}" y="{ay + r * lh:.1f}">{text}</text>')
    return "".join(out)
