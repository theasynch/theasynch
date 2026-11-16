"""Turn an image into a grid of characters, and know which chip block each cell belongs to.

Default source is a procedurally drawn chip die. Drop a `source-photo.png` into the
repo root and set "mode": "photo" in data/profile.json to use a portrait instead
(a portrait has no blocks, so it gets a generic twinkle animation).
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

RAMP = " .:-=+*#%@"  # light -> dense
SIZE = 800

# functional blocks of the die, as fractions of the core area (x0, y0, x1, y1)
BLOCKS = {
    "cpu":   (0.00, 0.00, 0.58, 0.56),
    "sramA": (0.62, 0.00, 1.00, 0.26),
    "sramB": (0.62, 0.30, 1.00, 0.56),
    "pll":   (0.00, 0.62, 0.30, 1.00),
    "snn":   (0.34, 0.62, 0.74, 1.00),
    "pmu":   (0.78, 0.62, 1.00, 1.00),
}
PAD_N, PAD_W = 16, 28


def geom(size=SIZE):
    m = int(size * 0.035)
    s = m + 24
    inset = s + 14
    c0 = int(size * 0.19)
    return {"m": m, "s": s, "inset": inset, "c0": c0, "cw": size - 2 * c0}


def pad_positions(size=SIZE):
    """Normalised (0..1) positions of the bond pads along one die edge."""
    g = geom(size)
    span = size - 2 * g["inset"] - PAD_W
    return [(g["inset"] + i * span / PAD_N + PAD_W / 2) / size for i in range(PAD_N + 1)]


def block_rect(name, size=SIZE):
    g = geom(size)
    a, b, c, d = BLOCKS[name]
    return (g["c0"] + a * g["cw"], g["c0"] + b * g["cw"], g["c0"] + c * g["cw"], g["c0"] + d * g["cw"])


def die_image(size=SIZE):
    im = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(im)
    g = geom(size)
    m, s, inset, c0, cw = g["m"], g["s"], g["inset"], g["c0"], g["cw"]

    d.rectangle([m, m, size - m, size - m], outline=0, width=12)          # die edge
    d.rectangle([s, s, size - s, size - s], outline=100, width=4)         # seal ring

    span = size - 2 * inset - PAD_W                                         # bond pads
    for i in range(PAD_N + 1):
        p = inset + i * span / PAD_N
        for x, y in [(p, inset), (p, size - inset - PAD_W), (inset, p), (size - inset - PAD_W, p)]:
            d.rectangle([x, y, x + PAD_W, y + PAD_W], fill=25)

    # CPU: standard-cell rows + register file + ALU
    x0, y0, x1, y1 = block_rect("cpu")
    d.rectangle([x0, y0, x1, y1], outline=0, width=7)
    y = y0 + 10
    while y < y1 - 6:
        d.line([x0 + 8, y, x1 - 8, y], fill=70, width=4)
        y += 9
    rx0, ry0 = x0 + 0.05 * cw, y0 + 0.08 * cw
    rx1, ry1 = x0 + 0.27 * cw, y0 + 0.30 * cw
    d.rectangle([rx0, ry0, rx1, ry1], fill=255, outline=0, width=5)
    for k in range(int(rx0) + 8, int(rx1), 10):
        d.line([k, ry0 + 6, k, ry1 - 6], fill=20, width=4)
    d.rectangle([x0 + 0.32 * cw, y0 + 0.34 * cw, x0 + 0.54 * cw, y0 + 0.52 * cw], fill=70)

    # two SRAM macros: dense bitcell grid
    for name in ("sramA", "sramB"):
        x0, y0, x1, y1 = block_rect(name)
        d.rectangle([x0, y0, x1, y1], outline=0, width=7)
        k = x0 + 8
        while k < x1 - 4:
            d.line([k, y0 + 6, k, y1 - 6], fill=15, width=3)
            k += 8
        k = y0 + 8
        while k < y1 - 4:
            d.line([x0 + 6, k, x1 - 6, k], fill=15, width=3)
            k += 8

    # analog / PLL: concentric rings
    x0, y0, x1, y1 = block_rect("pll")
    d.rectangle([x0, y0, x1, y1], outline=0, width=7)
    off = 14
    while x0 + off < x1 - off and y0 + off < y1 - off:
        d.rectangle([x0 + off, y0 + off, x1 - off, y1 - off], outline=40, width=5)
        off += 15

    # neuron array: dots + synapse lines
    x0, y0, x1, y1 = block_rect("snn")
    d.rectangle([x0, y0, x1, y1], outline=0, width=7)
    gx = x0 + 22
    while gx < x1 - 14:
        gy = y0 + 22
        while gy < y1 - 14:
            d.ellipse([gx - 8, gy - 8, gx + 8, gy + 8], fill=0)
            d.line([gx, gy, gx + 24, gy], fill=120, width=3)
            gy += 24
        gx += 24

    # power management: diagonal hatch
    x0, y0, x1, y1 = block_rect("pmu")
    d.rectangle([x0, y0, x1, y1], outline=0, width=7)
    k = -int(y1 - y0)
    while k < int(x1 - x0):
        d.line([x0 + k, y1, x0 + k + (y1 - y0), y0], fill=40, width=4)
        k += 14

    sx = c0 + 36                                                            # power straps
    while sx < c0 + cw:
        d.line([sx, c0 - 14, sx, c0 + cw + 14], fill=200, width=5)
        sx += 74
    return im


def photo_image(path, cols, rows, cell_aspect):
    im = Image.open(path).convert("L")
    target = (cols * cell_aspect) / rows
    w, h = im.size
    if w / h > target:
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = ImageOps.autocontrast(im, cutoff=2)
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=120))


def to_ascii(img, cols, rows, gamma=0.7, invert=False):
    small = img.resize((cols, rows), Image.BOX)
    px = small.load()
    out = []
    for y in range(rows):
        row = []
        for x in range(cols):
            v = (255 - px[x, y]) / 255.0
            if invert:
                v = 1 - v
            v = min(1.0, max(0.0, v)) ** gamma
            row.append(RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))])
        out.append("".join(row))
    return out


def region_map(cols, rows, size=SIZE):
    """For every character cell: which die block does its centre fall in?"""
    g = geom(size)
    rects = {n: block_rect(n, size) for n in BLOCKS}
    c0, cw, m = g["c0"], g["cw"], g["m"]
    out = []
    for r in range(rows):
        row = []
        for c in range(cols):
            x, y = (c + 0.5) * size / cols, (r + 0.5) * size / rows
            lab = None
            for name, (x0, y0, x1, y1) in rects.items():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    lab = name
                    break
            if lab is None:
                if c0 <= x <= c0 + cw and c0 <= y <= c0 + cw:
                    lab = "core"
                elif m <= x <= size - m and m <= y <= size - m:
                    lab = "ring"
            row.append(lab)
        out.append(row)
    return out


def build_ascii(cfg, root, cell_aspect=0.6):
    """Returns (lines, labels). labels is None for photos (no blocks to animate)."""
    cols, rows = cfg.get("cols", 100), cfg.get("rows", 60)
    photo = root / cfg.get("photo", "source-photo.png")
    if cfg.get("mode") == "photo" and photo.exists():
        img = photo_image(photo, cols, rows, cell_aspect)
        return to_ascii(img, cols, rows, invert=cfg.get("invert", False)), None
    return to_ascii(die_image(), cols, rows), region_map(cols, rows)
