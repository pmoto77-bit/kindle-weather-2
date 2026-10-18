"""Line-drawn weather icons (matching the approved mockups). s ~ half-width in px."""
import math

BLACK, DARK, WHITE = 0, 70, 255


def _blob(d, circles, fill, grow=0):
    for (x, y, r) in circles:
        r += grow
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def cloud(d, cx, cy, s, fill=WHITE, line=BLACK):
    c = [(cx - 0.45 * s, cy + 0.10 * s, 0.38 * s),
         (cx + 0.05 * s, cy - 0.18 * s, 0.50 * s),
         (cx + 0.55 * s, cy + 0.12 * s, 0.36 * s)]
    w = max(3, int(s * 0.09))
    base = [cx - 0.80 * s, cy + 0.05 * s, cx + 0.88 * s, cy + 0.48 * s]
    _blob(d, c, line, grow=w)
    d.rounded_rectangle([base[0] - w, base[1] - w, base[2] + w, base[3] + w],
                        radius=int(0.22 * s) + w, fill=line)
    _blob(d, c, fill)
    d.rounded_rectangle(base, radius=int(0.22 * s), fill=fill)


def sun(d, cx, cy, s):
    r = 0.55 * s
    w = max(3, int(r * 0.16))
    for i in range(8):
        a = i * math.pi / 4
        d.line([cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35,
                cx + math.cos(a) * r * 1.80, cy + math.sin(a) * r * 1.80], fill=BLACK, width=w)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLACK, width=w)


def moon(d, cx, cy, s):
    r = 0.62 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DARK)
    o = 0.45 * r
    d.ellipse([cx - r + o, cy - r - o * 0.4, cx + r + o, cy + r - o * 0.4], fill=WHITE)


def partly(d, cx, cy, s):
    r = 0.38 * s
    sx, sy = cx - 0.30 * s, cy - 0.30 * s
    w = max(3, int(r * 0.16))
    for i in range(8):
        a = i * math.pi / 4
        d.line([sx + math.cos(a) * r * 1.35, sy + math.sin(a) * r * 1.35,
                sx + math.cos(a) * r * 1.85, sy + math.sin(a) * r * 1.85], fill=BLACK, width=w)
    d.ellipse([sx - r, sy - r, sx + r, sy + r], outline=BLACK, width=w)
    cloud(d, cx + 0.15 * s, cy + 0.15 * s, 0.85 * s)


def moon_partly(d, cx, cy, s):
    moon(d, cx - 0.30 * s, cy - 0.30 * s, 0.65 * s)
    cloud(d, cx + 0.15 * s, cy + 0.15 * s, 0.85 * s)


def fog(d, cx, cy, s):
    cloud(d, cx, cy - 0.25 * s, s)
    w = max(3, int(s * 0.08))
    for i, (dx0, dx1) in enumerate(((-0.8, 0.6), (-0.5, 0.9), (-0.8, 0.4))):
        y = cy + 0.45 * s + i * 0.22 * s
        d.line([cx + dx0 * s, y, cx + dx1 * s, y], fill=BLACK, width=w)


def _drops(d, cx, cy, s, xs):
    w = max(3, int(s * 0.09))
    for i, dx in enumerate(xs):
        x = cx + dx * s
        y = cy + 0.45 * s + (0.08 * s if i == 1 else 0)
        d.line([x, y, x - 0.15 * s, y + 0.40 * s], fill=BLACK, width=w)


def _dots(d, cx, cy, s, pts):
    r = max(3, int(s * 0.08))
    for dx, dy in pts:
        x, y = cx + dx * s, cy + dy * s
        d.ellipse([x - r, y - r, x + r, y + r], fill=BLACK)


def rain(d, cx, cy, s):
    cloud(d, cx, cy - 0.25 * s, s)
    _drops(d, cx, cy, s, (-0.45, 0.0, 0.45))


def snow(d, cx, cy, s):
    cloud(d, cx, cy - 0.25 * s, s)
    _dots(d, cx, cy, s, ((-0.45, 0.55), (0.0, 0.70), (0.45, 0.55), (-0.22, 0.95), (0.22, 0.95)))


def ice(d, cx, cy, s):
    """Freezing rain: alternating drops and pellets."""
    cloud(d, cx, cy - 0.25 * s, s)
    _drops(d, cx, cy, s, (-0.45, 0.45))
    _dots(d, cx, cy, s, ((0.0, 0.62), (-0.2, 0.98), (0.25, 0.98)))


def storm(d, cx, cy, s):
    cloud(d, cx, cy - 0.25 * s, s)
    bolt = [(cx + 0.05 * s, cy + 0.30 * s), (cx - 0.25 * s, cy + 0.72 * s),
            (cx - 0.02 * s, cy + 0.72 * s), (cx - 0.18 * s, cy + 1.10 * s),
            (cx + 0.28 * s, cy + 0.55 * s), (cx + 0.03 * s, cy + 0.55 * s),
            (cx + 0.20 * s, cy + 0.30 * s)]
    d.polygon(bolt, fill=BLACK)


def warning(d, cx, cy, s, fg=WHITE, bg=BLACK):
    """Triangle with '!' (fonts lack the warning glyph)."""
    pts = [(cx, cy - s), (cx + 1.1 * s, cy + 0.85 * s), (cx - 1.1 * s, cy + 0.85 * s)]
    d.polygon(pts, fill=fg)
    w = max(2, int(s * 0.22))
    d.line([cx, cy - 0.35 * s, cx, cy + 0.25 * s], fill=bg, width=w)
    d.ellipse([cx - w * 0.6, cy + 0.45 * s - w * 0.6, cx + w * 0.6, cy + 0.45 * s + w * 0.6], fill=bg)


ICONS = {"clear": sun, "partly": partly, "cloud": cloud, "fog": fog, "rain": rain,
         "snow": snow, "ice": ice, "storm": storm, "moon": moon, "moon_partly": moon_partly}


def draw(d, kind, cx, cy, s):
    ICONS[kind](d, cx, cy, s)
