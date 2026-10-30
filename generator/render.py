"""Draw a day as a grayscale PNG in the approved Layout C ('Time of day').

The layout is written in PW1 pixels (758x1024, "layout units"). ScaledDraw multiplies
every coordinate, line width, radius and font size by screen width / 758, so the same
layout comes out sharp on a PW3 (1072x1448, x1.414) and fits exactly the same way.

The fit rule (never cut off, never cram): render, measure, and if the content runs into
the footer, step down: drop reasons (lowest priority first) -> curve 90->60 px ->
drop curve (only when the alert banner shows) -> drop lowest-priority item.
"""
import os
from collections import Counter
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont

import holidays
import icons
from rules import PRECIP_RANK, aqi_line, category, clock, trim_reasons, wear_list

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_FILES = {"regular": "selawk.ttf", "bold": "selawkb.ttf", "semi": "selawksb.ttf",
              "light": "selawkl.ttf", "semilight": "selawksl.ttf"}
BLACK, DARK, MID, LIGHT, WHITE = 0, 70, 120, 175, 255
M = 40              # side margin
FOOTER_H = 74       # footer rule sits this far above the bottom edge
ITEM_H, REASON_H, WRAP_H = 48, 30, 40
SEVERITY = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
BASE_W = 758        # layout units are PW1 pixels

_fonts = {}


def font(size, weight="regular"):
    key = (size, weight)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(HERE, "fonts", FONT_FILES[weight]), size)
    return _fonts[key]


def scaled_font(f, s):
    key = (f.path, f.size * s)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(f.path, f.size * s)
    return _fonts[key]


def screen(cfg):
    """(layout width, layout height, scale) for the configured screen."""
    s = cfg["screen"]["width"] / BASE_W
    return BASE_W, round(cfg["screen"]["height"] / s), s


class LayoutError(Exception):
    pass


class ScaledDraw:
    """ImageDraw that takes layout units. At scale 1 it passes everything through untouched."""

    def __init__(self, img, s):
        self.raw, self.s = ImageDraw.Draw(img), s

    def _xy(self, xy):
        if self.s == 1:
            return xy
        return [tuple(v * self.s for v in p) if isinstance(p, (tuple, list)) else p * self.s
                for p in xy]

    def _kw(self, kw):
        if self.s != 1:
            if "width" in kw:
                kw["width"] = max(1, round(kw["width"] * self.s))
            if "radius" in kw:
                kw["radius"] = kw["radius"] * self.s
        return kw

    def _font(self, f):
        return f if self.s == 1 else scaled_font(f, self.s)

    def line(self, xy, **kw):
        self.raw.line(self._xy(xy), **self._kw(kw))

    def polygon(self, xy, **kw):
        self.raw.polygon(self._xy(xy), **self._kw(kw))

    def ellipse(self, xy, **kw):
        self.raw.ellipse(self._xy(xy), **self._kw(kw))

    def rectangle(self, xy, **kw):
        self.raw.rectangle(self._xy(xy), **self._kw(kw))

    def rounded_rectangle(self, xy, **kw):
        self.raw.rounded_rectangle(self._xy(xy), **self._kw(kw))

    def text(self, xy, s, font, **kw):
        self.raw.text(self._xy(xy), s, font=self._font(font), **kw)

    def textbbox(self, xy, s, font, **kw):
        b = self.raw.textbbox(self._xy(xy), s, font=self._font(font), **kw)
        return b if self.s == 1 else tuple(v / self.s for v in b)

    def textlength(self, s, font):
        n = self.raw.textlength(s, font=self._font(font))
        return n if self.s == 1 else n / self.s


class Canvas:
    """Thin wrapper that remembers every text box (for the overlap test). w and h are
    layout units; the image is (w, h) x scale."""

    def __init__(self, w, h, s=1):
        self.w, self.h = w, h
        self.img = Image.new("L", (round(w * s), round(h * s)), WHITE)
        self.d = ScaledDraw(self.img, s)
        self.boxes = []

    def text(self, xy, s, f, fill=BLACK, anchor="la"):
        self.d.text(xy, s, font=f, fill=fill, anchor=anchor)
        self.boxes.append((self.d.textbbox(xy, s, font=f, anchor=anchor), s))

    def width(self, s, f):
        return self.d.textlength(s, font=f)

    def paste(self, im, x, y, w, h):
        """Paste a grayscale picture into the layout box (x, y, w, h), scaled smoothly."""
        s = self.d.s
        self.img.paste(im.resize((round(w * s), round(h * s)), Image.LANCZOS), (round(x * s), round(y * s)))

    def rule(self, y, fill=LIGHT, width=2):
        self.d.line([M, y, self.w - M, y], fill=fill, width=width)


# ------------------------------------------------------------------ text helpers
def time12(hhmm):
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"


def wrap(c, s, f, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and c.width(trial, f) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def ellipsize(c, s, f, max_w):
    if c.width(s, f) <= max_w:
        return s
    while s and c.width(s + "…", f) > max_w:
        s = s[:-1]
    return s.rstrip() + "…"


# ------------------------------------------------------------------ views
def column_view(day, w):
    hrs = [x for x in day["hours"] if w["start"] <= x["h"] <= w["end"]]
    temp = round(sum(x["temp"] for x in hrs) / len(hrs))
    feels = round(sum(x["feels"] for x in hrs) / len(hrs))
    wet = [category(x["code"]) for x in hrs
           if x["pop"] >= 40 and category(x["code"]) in PRECIP_RANK]
    if wet:
        kind = max(wet, key=PRECIP_RANK.get)
    else:
        sky = [c if c in ("clear", "partly", "cloud", "fog") else "cloud"
               for c in (category(x["code"]) for x in hrs)]
        kind = Counter(sky).most_common(1)[0][0]
    if sum(not x["is_day"] for x in hrs) > len(hrs) / 2:
        kind = {"clear": "moon", "partly": "moon_partly"}.get(kind, kind)
    pop = max(x["pop"] for x in hrs)
    if pop < 20:
        precip = "dry"
    else:
        cats = [category(x["code"]) for x in hrs
                if x["pop"] >= 20 and category(x["code"]) in PRECIP_RANK]
        word = max(cats, key=PRECIP_RANK.get) if cats else ("snow" if temp <= 32 else "rain")
        precip = f"{'storms' if word == 'storm' else word} {pop}%"
    return {"name": w["name"], "label": w["label"], "icon": kind,
            "temp": temp, "feels": feels, "precip": precip}


def banner_text(day):
    alerts = day.get("alerts") or []
    if not alerts:
        return None
    alerts = sorted(alerts, key=lambda a: SEVERITY.get(a["severity"], 9))
    top = alerts[0]
    s = top["event"].upper()
    if top.get("ends"):
        end = datetime.fromisoformat(top["ends"])
        when = clock(end.hour) if end.minute == 0 else time12(top["ends"][11:16])
        if when == "noon":
            when = "12 PM"
        s += f" until {when}" + ("" if end.date().isoformat() == day["date"] else f" {end:%a}")
    if len(alerts) > 1:
        s += f"  +{len(alerts) - 1} more"
    return s


def notes(day):
    missing = []
    if day.get("alerts") is None:
        missing.append("weather alerts")
    if day.get("aqi") is None:
        missing.append("air quality")
    if not missing:
        return None
    s = " and ".join(missing)
    return f"{s[0].upper()}{s[1:]} unavailable this update"


# ------------------------------------------------------------------ blocks
def draw_header(c, day):
    d = date.fromisoformat(day["date"])
    title = f"{d:%A}, {d:%b} {d.day}".upper()
    hilo = f"{day['hi']}° / {day['lo']}°"
    y = 30
    if day["label"] == "tomorrow":
        f = font(18, "bold")
        tw = c.width("TOMORROW", f)
        c.d.rounded_rectangle([M, 10, M + tw + 20, 36], radius=6, fill=BLACK)
        c.text((M + 10, 23), "TOMORROW", f, fill=WHITE, anchor="lm")
        y = 40
    size = 42
    while size > 32 and (c.width(title, font(size, "bold")) +
                         c.width(hilo, font(size, "light")) + 24 > c.w - 2 * M):
        size -= 2
    c.text((M, y), title, font(size, "bold"))
    c.text((c.w - M, y), hilo, font(size, "light"), anchor="ra")
    c.rule(y + 70, fill=BLACK, width=3)
    return y + 70


def draw_banner(c, y, s):
    h = 58
    c.d.rectangle([0, y, c.w, y + h], fill=BLACK)
    icons.warning(c.d, M + 16, y + h / 2, 15)
    size = 26
    while size > 20 and c.width(s, font(size, "bold")) > c.w - 2 * M - 46:
        size -= 1
    s = ellipsize(c, s, font(size, "bold"), c.w - 2 * M - 46)
    c.text((M + 46, y + h / 2), s, font(size, "bold"), fill=WHITE, anchor="lm")
    return y + h


def draw_columns(c, y0, cols):
    colw = (c.w - 2 * M) / 3
    for i, col in enumerate(cols):
        cx = M + colw * i + colw / 2
        if i:
            c.d.line([M + colw * i, y0, M + colw * i, y0 + 288], fill=LIGHT, width=2)
        c.text((cx, y0), col["name"], font(26, "bold"), anchor="ma")
        c.text((cx, y0 + 33), col["label"], font(22), fill=MID, anchor="ma")
        icons.draw(c.d, col["icon"], cx, y0 + 108, 44)
        c.text((cx, y0 + 160), f"{col['temp']}°", font(52, "bold"), anchor="ma")
        c.text((cx, y0 + 232), col["precip"], font(24, "semi"), fill=DARK, anchor="ma")
        c.text((cx, y0 + 263), f"feels {col['feels']}°", font(22), fill=MID, anchor="ma")
    c.rule(y0 + 306)
    return y0 + 306


def draw_curve(c, y, day, cfg, ch):
    h0, h1 = cfg["curve_hours"]
    temps = [x["temp"] for x in day["hours"] if h0 <= x["h"] <= h1]
    x0, x1 = M + 10, c.w - M - 10
    top, bot = y + 34, y + 34 + ch
    fl = font(24, "bold")
    floor = bot - 14 - (fl.getbbox("0°", anchor="ma")[3])  # room for the low label under its dot
    lo, hi = min(temps) - 2, max(temps) + 2
    n = len(temps)
    pts = [(x0 + i * (x1 - x0) / (n - 1), floor - (t - lo) / (hi - lo) * (floor - top))
           for i, t in enumerate(temps)]
    c.d.polygon(pts + [(x1, bot), (x0, bot)], fill=230)
    c.d.line(pts, fill=BLACK, width=4, joint="curve")
    pk = max(range(n), key=lambda i: temps[i])
    lk = min(range(n), key=lambda i: temps[i])
    marks = [(pk, -12, "mb")] + ([(lk, 12, "ma")] if temps[lk] < temps[pk] else [])  # flat day: high only
    for k, dy, anchor in marks:
        px, py = pts[k]
        c.d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=BLACK)
        c.text((min(max(px, M + 24), c.w - M - 24), py + dy), f"{temps[k]}°", fl, anchor=anchor)
    f = font(20)
    for i in range(0, n, 4):
        h = h0 + i
        lab = f"{(h - 1) % 12 + 1}{'a' if h < 12 else 'p'}"
        c.text((pts[i][0], bot + 6), lab, f, fill=MID, anchor="ma")
    c.rule(bot + 40)
    return bot + 40


def draw_aqi(c, y, s):
    c.text((M, y + 12), s, font(26, "semi"), fill=DARK)
    return y + 50


def draw_wear(c, y, wear):
    c.text((M, y + 14), "WHAT TO WEAR", font(28, "bold"))
    top = y + 50
    f_item, f_why = font(32), font(23)
    max_w = c.w - 2 * M - 30
    for it in wear:
        lines = wrap(c, it["text"], f_item, max_w)
        cy = top + ITEM_H / 2
        c.d.rectangle([M + 4, cy - 4, M + 16, cy + 8], fill=BLACK)
        for k, line in enumerate(lines):
            c.text((M + 30, cy + k * WRAP_H), line, f_item, anchor="lm")
        top += ITEM_H + WRAP_H * (len(lines) - 1)
        if it["reason"]:
            c.text((M + 30, top + 8), ellipsize(c, it["reason"], f_why, max_w), f_why,
                   fill=MID, anchor="lm")
            top += REASON_H
    return top


def draw_note(c, y, s):
    icons.warning(c.d, M + 10, y + 18, 9, fg=DARK, bg=WHITE)
    c.text((M + 30, y + 18), s, font(22), fill=DARK, anchor="lm")
    return y + 36


def _overlaps(a, b, pad=8):
    return a[0] - pad < b[2] and b[0] < a[2] + pad and a[1] - pad < b[3] and b[1] < a[3] + pad


_art = {}


def holiday_image(key):
    """OpenMoji art prepared by make_holiday_art.py (generator/holiday_art/<key>.png), or None."""
    if key not in _art:
        path = os.path.join(HERE, "holiday_art", key + ".png")
        _art[key] = Image.open(path).convert("L") if os.path.exists(path) else None
    return _art[key]


def draw_holiday(c, key, top):
    """Holiday art in the empty bottom-right corner: the biggest size that fits below `top`
    without touching any text, or nothing at all (never crammed)."""
    im, caption = holiday_image(key), holidays.CAPTION[key]
    if im is None:
        return None
    f = font(18, "semi")
    bottom = c.h - FOOTER_H - 8
    for s in (150, 125, 100):
        w = max(s, c.width(caption, f))
        box = (c.w - M - w, bottom - s - 26, c.w - M, bottom)
        if box[1] < top or any(_overlaps(box, b) for b, _ in c.boxes):
            continue
        k = s / max(im.size)   # fit inside the s x s square, keeping its shape
        iw, ih = im.width * k, im.height * k
        c.paste(im, box[2] - w / 2 - iw / 2, box[1] + (s - ih) / 2, iw, ih)
        c.text((box[2] - w / 2, bottom), caption, f, fill=DARK, anchor="md")
        return key
    return None


def draw_footer(c, day):
    y = c.h - FOOTER_H
    c.rule(y)
    c.text((M, y + 36), f"Sunrise {time12(day['sunrise'])}  ·  Sunset {time12(day['sunset'])}",
           font(22), fill=DARK, anchor="lm")
    c.text((c.w - M, y + 36), f"Updated {time12(day['updated'])}", font(20), fill=MID, anchor="rm")


# ------------------------------------------------------------------ compose + fit
def compose(day, cfg, state):
    c = Canvas(*screen(cfg))
    y = draw_header(c, day)
    if state["banner"]:
        y = draw_banner(c, y + 10, state["banner"])
    y = draw_columns(c, y + 16, [column_view(day, w) for w in cfg["windows"]])
    if state["curve"]:
        y = draw_curve(c, y, day, cfg, state["curve_h"])
    if state["aqi"]:
        y = draw_aqi(c, y, state["aqi"])
    wear_top = y
    y = draw_wear(c, y, state["wear"])
    if state["note"]:
        y = draw_note(c, y + 4, state["note"])
    draw_footer(c, day)
    c.holiday = draw_holiday(c, state["holiday"], wear_top) if state.get("holiday") else None
    return c, y


def _fit(day, cfg, rules, base):
    """Fullest layout that fits. Within each curve size, drop reasons (lowest priority
    first) before shrinking the curve; the curve may only be dropped under a banner;
    items go last."""
    limit = screen(cfg)[1] - FOOTER_H - 10
    levels = [(True, 90, None), (True, 60, "curve 60px")]
    if base["banner"]:
        levels.append((False, 0, "dropped curve"))
    wear = [dict(i) for i in base["wear"]]
    item_drops = []
    while True:
        for curve, ch, note in levels:
            n = sum(1 for i in wear if i["reason"])
            for keep in range(n, -1, -1):
                trial = [dict(i) for i in wear]
                dropped = trim_reasons(trial, rules, keep)
                state = {**base, "wear": trial, "curve": curve, "curve_h": ch}
                c, bottom = compose(day, cfg, state)
                if bottom <= limit:
                    actions = item_drops + [f"dropped {t} reason" for t in dropped]
                    return c, bottom, state, actions + ([note] if note else [])
        if len(wear) <= 1:
            raise LayoutError(f"{day['date']}: content does not fit")
        item_drops.append(f"dropped {wear.pop()['key']} item")


def render(day, rules, cfg):
    """Return (PIL image, info dict). info['fit'] lists any fit-rule steps taken."""
    base = {"banner": banner_text(day), "aqi": aqi_line(day, rules), "note": notes(day),
            "holiday": holidays.holiday(day["date"]),
            "wear": wear_list(day, rules, cfg)}
    c, bottom, state, actions = _fit(day, cfg, rules, base)
    img = c.img.point(lambda v: (v // 17) * 17)  # e-ink shows 16 gray levels
    info = {"date": day["date"], "label": day["label"], "fit": actions, "bottom": bottom, "holiday": c.holiday,
            "wear": [i["text"] for i in state["wear"]],
            "reasons": [i["reason"] for i in state["wear"] if i["reason"]],
            "banner": state["banner"], "aqi_line": state["aqi"], "boxes": c.boxes}
    return img, info
