#!/usr/bin/env python3
"""Generate the README cards (SVG) from data/profile.json + live GitHub activity.

Theme: classic PCB. Solder-mask green boards, silkscreen-white text, ENIG-gold accents.

Run locally:   python scripts/build.py
Run in CI:     see .github/workflows/refresh.yml (daily)
"""
import datetime as dt
import html
import json
import math
import os
import random
import re
import sys
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chip_anim  # noqa: E402
from ascii_art import build_ascii, geom, pad_positions  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
P = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
USER = os.environ.get("GH_USER", P["github_user"])

# ---- theme: PCB ------------------------------------------------------------
BG_TOP, BG_BOT = "#0f6b3d", "#0a5130"        # solder mask
BORDER = "#1c8f55"
INK = "#f3f8f1"                                # silkscreen white
SOFT, MUTED, FAINT = "#d3ecdc", "#a6d2b4", "#6aa782"
GOLD = chip_anim.GOLD                          # ENIG gold
LED = chip_anim.LED                            # status-LED green
PANEL, PANEL_LINE = "#094a2b", "#1f8a4f"
TRACE, VIA = "#1f9d5c", "#083d25"
LEVELS = ["#0a4a2a", "#1d8a4e", "#34b568", "#6fdc92", "#c9ffd9"]

SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
W, PAD = 830, 40
INNER = W - 2 * PAD
REDUCE = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
esc = html.escape


# ---- text -> outlines (so the serif renders identically everywhere) -------
class Face:
    def __init__(self, path):
        self.f = TTFont(path)
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upem = self.f["head"].unitsPerEm

    def width(self, text, size):
        s = size / self.upem
        return sum(self.gs[self.cmap.get(ord(c), ".notdef")].width for c in text) * s

    def path(self, text, size, x, y):
        s, cur, d = size / self.upem, 0.0, []
        for c in text:
            g = self.cmap.get(ord(c), ".notdef")
            pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.1f}")
            self.gs[g].draw(TransformPen(pen, (s, 0, 0, -s, x + cur * s, y)))
            d.append(pen.getCommands())
            cur += self.gs[g].width
        return " ".join(d)

    def fit(self, text, max_w, max_size):
        return min(max_size, max_size * max_w / max(self.width(text, max_size), 1))


REG = Face(ROOT / "fonts" / "InstrumentSerif-Regular.ttf")
ITA = Face(ROOT / "fonts" / "InstrumentSerif-Italic.ttf")


def serif(parts, size, x, y):
    out = []
    for face, text, col in parts:
        out.append(f'<path d="{face.path(text, size, x, y)}" fill="{col}"/>')
        x += face.width(text, size)
    return "".join(out), x


def title(parts, y=86, size=46):
    return serif([(REG, parts[0], INK), (ITA, parts[1], GOLD)], size, PAD, y)[0]


def txt(x, y, s, size=12, fill=INK, font=MONO, weight=400, anchor="start", ls=0, cls=""):
    extra = (f' letter-spacing="{ls}"' if ls else "") + (f' class="{cls}"' if cls else "")
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def card(h, inner, label, defs="", style=""):
    holes = "".join(
        f'<circle cx="{x}" cy="{y}" r="8.5" fill="#c9a24a" fill-opacity=".5"/>'
        f'<circle cx="{x}" cy="{y}" r="4.2" fill="#052a18"/>'
        for x, y in [(24, 24), (W - 24, 24), (24, h - 24), (W - 24, h - 24)])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOT}"/></linearGradient>{defs}</defs>'
            f'<style>{style}{REDUCE}</style>'
            f'<rect x=".5" y=".5" width="{W-1}" height="{h-1}" rx="28" fill="url(#bg)" stroke="{BORDER}"/>'
            f'{holes}{inner}</svg>')


def write(name, svg):
    (OUT / name).write_text(svg, encoding="utf-8")
    print(f"wrote assets/{name} ({len(svg)//1024} KB)")


# ---- contributions ---------------------------------------------------------
def fetch_contribs(user):
    cache = ROOT / "data" / "contribs-cache.json"
    try:
        req = urllib.request.Request(
            f"https://github.com/users/{user}/contributions",
            headers={"User-Agent": "Mozilla/5.0 (readme-card-builder)"})
        page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        tips = {m.group(1): m.group(2) for m in re.finditer(
            r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page)}
        days = []
        for m in re.finditer(r"<td\b[^>]*ContributionCalendar-day[^>]*>", page):
            tag = m.group(0)
            date = re.search(r'data-date="([\d-]+)"', tag)
            cid = re.search(r'\bid="([^"]+)"', tag)
            lvl = re.search(r'data-level="(\d)"', tag)
            if not (date and cid and lvl):
                continue
            n = re.match(r"(\d+) contribution", tips.get(cid.group(1), "").strip())
            days.append({"date": date.group(1), "level": int(lvl.group(1)),
                         "count": int(n.group(1)) if n else 0})
        if not days:
            raise ValueError("no cells parsed")
        days.sort(key=lambda d: d["date"])
        cache.write_text(json.dumps(days), encoding="utf-8")
        return days
    except Exception as e:  # network/markup hiccup: reuse last good data
        print(f"! live fetch failed ({e}); using cache", file=sys.stderr)
        if cache.exists():
            return json.loads(cache.read_text())
        raise


def streaks(days):
    today = dt.date.today().isoformat()
    counts = [d["count"] for d in days if d["date"] <= today]
    best = run = 0
    for c in counts:
        run = run + 1 if c else 0
        best = max(best, run)
    cur, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    while i >= 0 and counts[i]:
        cur += 1
        i -= 1
    return cur, best


# ---- card 1: hero (animated) -----------------------------------------------
SIG_PERIOD, SIG_DASH = 2.0, 60          # signal pulses on the board traces
BEAM_PERIOD, BEAM_H, LED_PERIOD = 6.0, 36, 3.0


def hero(t=None):
    """t=None -> the real CSS-animated SVG. t=<seconds> -> a still frame (used for previews)."""
    H, col_w = 420, 420
    lines, labels = build_ascii(P["ascii"], ROOT)
    cols, rows = len(lines[0]), len(lines)
    cw, lh, fs = 3.0, 5.0, 5.0
    gw, gh = cols * cw, rows * lh
    ax, ay = W - PAD - gw + 4, (H - gh) / 2 + 4
    g = geom()
    mn = g["m"] / 800
    die_l, die_r = ax + mn * gw, ax + (1 - mn) * gw
    die_t, die_b = ay + mn * gh, ay + (1 - mn) * gh

    # board traces fanning out of the die edge, ending in vias; pulses run along them
    rng = random.Random(7)
    pads = pad_positions()
    trace_svg, sig_svg = [], []
    sides = [("T", 32, True), ("B", 28, False), ("L", 24, True), ("R", 40, False)]  # (side, max len, inbound)
    k = 0
    for side, maxlen, inbound in sides:
        for p in pads:
            ln = rng.uniform(10, maxlen)
            if side == "T":
                x = ax + p * gw; a, b = (x, die_t), (x, die_t - ln)
            elif side == "B":
                x = ax + p * gw; a, b = (x, die_b), (x, die_b + ln)
            elif side == "L":
                y = ay + p * gh; a, b = (die_l, y), (die_l - ln, y)
            else:
                y = ay + p * gh; a, b = (die_r, y), (die_r + ln, y)
            s, e = (b, a) if inbound else (a, b)       # path direction = signal direction
            trace_svg.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
                             f'stroke="{TRACE}" stroke-width="1.8" stroke-linecap="round"/>'
                             f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="3.3" fill="{VIA}" stroke="{TRACE}" stroke-width="1.4"/>')
            d_off = (k % 6) * 0.33
            if t is None:
                sig_attr = f' class="sg g{k % 6}"'
            else:
                sig_attr = (f' stroke-dasharray="4 {SIG_DASH - 4}" '
                            f'stroke-dashoffset="{-SIG_DASH * (((t + d_off) % SIG_PERIOD) / SIG_PERIOD):.2f}"')
            sig_svg.append(f'<line{sig_attr} x1="{s[0]:.1f}" y1="{s[1]:.1f}" x2="{e[0]:.1f}" y2="{e[1]:.1f}" '
                           f'stroke="{LED}" stroke-width="2" stroke-linecap="round" stroke-opacity=".9"/>')
            k += 1

    o = ["".join(trace_svg), "".join(sig_svg)]

    # left column
    led_op = "" if t is None else f' fill-opacity="{0.4 + 0.6 * (1 - abs(((t % LED_PERIOD) / LED_PERIOD) * 2 - 1)):.3f}"'
    o.append(f'<circle cx="{PAD + 7}" cy="63" r="10" fill="{LED}" fill-opacity=".16"/>'
             f'<circle{" class=\"led\"" if t is None else ""}{led_op} cx="{PAD + 7}" cy="63" r="5.5" fill="{LED}"/>')
    o.append(txt(PAD + 26, 68, P["eyebrow"], 12.5, MUTED, ls=1.8))
    ns = min(REG.fit(P["name"], col_w, 138), ITA.fit(P["name_line2"], col_w, 138))  # one shared size
    base1 = 186
    base2 = base1 + ns * 0.82
    o.append(serif([(REG, P["name"], INK)], ns, PAD - 4, base1)[0])
    o.append(serif([(ITA, P["name_line2"], GOLD)], ns, PAD - 2, base2)[0])
    y = base2 + 44
    for line in P["tagline"]:
        o.append(txt(PAD, y, line, 19, SOFT, SANS))
        y += 28
    o.append(f'<text x="{PAD}" y="{y + 14}" font-family="{MONO}" font-size="15" fill="{INK}">'
             f'{esc(P["link"])} <tspan fill="{GOLD}">\u2197</tspan></text>')

    # the chip: every character belongs to a functional block
    cells, classes = chip_anim.assign(lines, labels, cw, lh)
    o.append(f'<g font-family="{MONO}" font-size="{fs}" fill="{chip_anim.BASE}" fill-opacity="{chip_anim.BOP}">'
             f'{chip_anim.emit(cells, classes, ax, ay, cw, lh, t)}</g>')
    o.append(txt(die_r, H - 18, "U1", 11, FAINT, anchor="end", ls=1.5))

    # scan-chain beam sweeping the die, clipped to it
    travel = gh + BEAM_H
    if t is None:
        beam_attr = ' class="beam"'
    else:
        ph = ((t % BEAM_PERIOD) / BEAM_PERIOD) / 0.6
        beam_attr = f' transform="translate(0 {travel * min(ph, 1):.1f})"'
    o.append(f'<g clip-path="url(#die)"><rect{beam_attr} x="{ax:.1f}" y="{ay - BEAM_H:.1f}" '
             f'width="{gw:.1f}" height="{BEAM_H}" fill="url(#beamg)"/></g>')

    defs = (f'<clipPath id="die"><rect x="{ax:.1f}" y="{ay:.1f}" width="{gw:.1f}" height="{gh:.1f}"/></clipPath>'
            f'<linearGradient id="beamg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#ffffff" stop-opacity="0"/>'
            f'<stop offset=".8" stop-color="#ffffff" stop-opacity=".10"/>'
            f'<stop offset="1" stop-color="#ffffff" stop-opacity=".18"/></linearGradient>')
    style = ""
    if t is None:
        sig_delays = "".join(f".g{i}{{animation-delay:-{i * 0.33:.2f}s}}" for i in range(6))
        style = (chip_anim.css(classes)
                 + f"@keyframes dash{{from{{stroke-dashoffset:0}}to{{stroke-dashoffset:-{SIG_DASH}}}}}"
                 + f".sg{{stroke-dasharray:4 {SIG_DASH - 4};animation:dash {SIG_PERIOD:g}s linear infinite}}" + sig_delays
                 + f"@keyframes beam{{0%{{transform:translateY(0)}}60%{{transform:translateY({travel:.0f}px)}}"
                   f"100%{{transform:translateY({travel:.0f}px)}}}}"
                 + f".beam{{animation:beam {BEAM_PERIOD:g}s linear infinite}}"
                 + f"@keyframes led{{0%,100%{{fill-opacity:.4}}50%{{fill-opacity:1}}}}"
                 + f".led{{animation:led {LED_PERIOD:g}s linear infinite}}")
    return card(H, "".join(o), f'{P["name"]} {P["name_line2"]}', defs, style)


# ---- card 2: heatmap -------------------------------------------------------
def heatmap(days):
    today = dt.date.today().isoformat()
    days = [d for d in days if d["date"] <= today]
    first = dt.date.fromisoformat(days[0]["date"])
    sunday0 = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cell_pos = {}
    for d in days:
        dd = dt.date.fromisoformat(d["date"])
        cell_pos[d["date"]] = ((dd - sunday0).days // 7, (dd.weekday() + 1) % 7)
    cols = max(c for c, _ in cell_pos.values()) + 1
    pitch = INNER / cols
    size, gy = pitch - 3.2, 124

    o = [title(P["heatmap_title"]), txt(W - PAD, 76, "REFRESHED DAILY", 12.5, MUTED, anchor="end", ls=1.8)]
    for d in days:
        c, r = cell_pos[d["date"]]
        n = d["count"]
        tip = f'{n} contribution{"" if n == 1 else "s"} on {d["date"]}'
        o.append(f'<rect x="{PAD + c * pitch:.1f}" y="{gy + r * pitch:.1f}" width="{size:.1f}" '
                 f'height="{size:.1f}" rx="2.8" fill="{LEVELS[d["level"]]}"><title>{tip}</title></rect>')

    last_label = -9
    for d in days:
        dd = dt.date.fromisoformat(d["date"])
        c, r = cell_pos[d["date"]]
        if r == 0 and dd.day <= 7 and c - last_label >= 3:
            o.append(txt(PAD + c * pitch, gy + 7 * pitch + 20, dd.strftime("%b"), 12.5, MUTED))
            last_label = c

    total = sum(d["count"] for d in days)
    y = gy + 7 * pitch + 58
    o.append(txt(PAD, y, f"{total} contributions in the last year", 12.5, MUTED, ls=0.4))
    lx = W - PAD - 190
    o.append(txt(lx, y, "less", 12.5, MUTED))
    for i, colr in enumerate(LEVELS):
        o.append(f'<rect x="{lx + 38 + i * 17}" y="{y - 11}" width="13" height="13" rx="3" fill="{colr}"/>')
    o.append(txt(lx + 38 + 5 * 17 + 4, y, "more", 12.5, MUTED))
    return card(int(y + 36), "".join(o), "GitHub contribution heatmap, refreshed daily"), total


# ---- card 3: stats ---------------------------------------------------------
def stats(days, total):
    cur, best = streaks(days)
    active = sum(1 for d in days if d["count"] > 0)
    items = [(str(total), "CONTRIBUTIONS", "last 12 months"),
             (str(cur), "CURRENT STREAK", "days in a row"),
             (str(best), "LONGEST STREAK", "days in a row"),
             (str(active), "ACTIVE DAYS", "last 12 months")]
    H, cw, o = 188, INNER / 4, []
    for i, (num, a, b) in enumerate(items):
        x = PAD + i * cw
        if i:
            o.append(f'<line x1="{x - 12:.1f}" y1="44" x2="{x - 12:.1f}" y2="{H - 44}" stroke="{BORDER}"/>')
        o.append(serif([(REG, num, GOLD if i == 0 else INK)], 78, x, 104)[0])
        o.append(txt(x, 138, a, 11.5, INK, ls=1.6))
        o.append(txt(x, 156, b, 11.5, MUTED))
    return card(H, "".join(o), "GitHub activity stats")


# ---- card 4: RTL -> GDSII flow --------------------------------------------
def flow():
    cols, gap, th = 5, 14, 116
    tw = (INNER - gap * (cols - 1)) / cols
    gy = 122
    o = [title(P["flow_title"])]
    label = {"solid": "SOLID", "building": "BUILDING", "progress": "IN PROGRESS", "queued": "QUEUED"}
    for i, st in enumerate(P["flow"]):
        x = PAD + (i % cols) * (tw + gap)
        y = gy + (i // cols) * (th + gap)
        s, dash = st["status"], ""
        if s == "solid":      # done: silkscreen-white plate
            fill, stroke, ink, sub, num = "#eaf5ec", "#eaf5ec", "#0a3d24", "#2f6b4a", "#0f6a3d"
        elif s == "building":  # lighter mask
            fill, stroke, ink, sub, num = "#1e8a4f", "#1e8a4f", "#ffffff", "#c4e8d0", "#e6f7ec"
        elif s == "progress":  # gold outline
            fill, stroke, ink, sub, num = PANEL, GOLD, "#ffffff", MUTED, GOLD
        else:                  # queued: unpopulated footprint
            fill, stroke, ink, sub, num = "none", FAINT, "#8fc2a2", "#6aa382", "#8fc2a2"
            dash = ' stroke-dasharray="4 4"'
        o.append(f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="16" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{2 if s == "progress" else 1.2}"{dash}/>')
        o.append(txt(x + 14, y + 26, st["n"], 12, num, weight=600))
        o.append(txt(x + tw - 14, y + 26, label[s], 9.5, num, anchor="end", ls=1))
        if s == "progress":
            o.append(f'<circle class="pulse" cx="{x + tw - 14 - len("IN PROGRESS") * 6.6 - 8:.1f}" cy="{y + 23}" r="3.2" fill="{GOLD}"/>')
        for j, ln in enumerate(st["name"]):
            o.append(txt(x + 14, y + 53 + j * 18, ln, 15, ink, SANS, 600))
        for j, ln in enumerate(st["tools"]):
            o.append(txt(x + 14, y + 91 + j * 14, ln, 10, sub))
    ly = gy + 2 * th + gap + 38
    lx = PAD
    for lab, fill, stroke, dash in [("solid", "#eaf5ec", "#eaf5ec", ""), ("building", "#1e8a4f", "#1e8a4f", ""),
                                     ("in progress", PANEL, GOLD, ""), ("queued", "none", FAINT, ' stroke-dasharray="3 3"')]:
        o.append(f'<rect x="{lx}" y="{ly - 11}" width="14" height="14" rx="4" fill="{fill}" stroke="{stroke}"{dash}/>')
        o.append(txt(lx + 22, ly, lab, 12, MUTED))
        lx += 22 + len(lab) * 7.4 + 26
    style = "@keyframes pulse{0%,100%{fill-opacity:1}50%{fill-opacity:.2}}.pulse{animation:pulse 1.8s linear infinite}"
    return card(ly + 34, "".join(o), "RTL to GDSII flow progress", style=style)


# ---- card 5: projects ------------------------------------------------------
def projects():
    gap, th = 16, 168
    tw = (INNER - gap) / 2
    gy = 122
    o = [title(P["projects_title"])]
    for i, pr in enumerate(P["projects"]):
        x = PAD + (i % 2) * (tw + gap)
        y = gy + (i // 2) * (th + gap)
        o.append(f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="18" fill="{PANEL}" stroke="{PANEL_LINE}"/>')
        o.append(txt(x + 22, y + 32, pr["tag"], 10.5, GOLD, weight=600, ls=1.4))
        o.append(serif([(REG, pr["name"], INK)], REG.fit(pr["name"], tw - 44, 40), x + 20, y + 74)[0])
        for j, ln in enumerate(pr["desc"]):
            o.append(txt(x + 22, y + 102 + j * 19, ln, 13.5, SOFT, SANS))
        cx = x + 22
        for chip in pr["chips"]:
            cwid = len(chip) * 6.3 + 18
            o.append(f'<rect x="{cx:.1f}" y="{y + 132}" width="{cwid:.1f}" height="22" rx="11" fill="none" stroke="#4f9b6c"/>')
            o.append(txt(cx + cwid / 2, y + 147, chip, 10.5, MUTED, anchor="middle"))
            cx += cwid + 8
    rows = (len(P["projects"]) + 1) // 2
    return card(gy + rows * th + (rows - 1) * gap + 40, "".join(o), "Selected projects")


if __name__ == "__main__":
    days = fetch_contribs(USER)
    heat, total = heatmap(days)
    write("hero.svg", hero())
    write("contrib-heatmap.svg", heat)
    write("stats.svg", stats(days, total))
    write("flow.svg", flow())
    write("projects.svg", projects())
