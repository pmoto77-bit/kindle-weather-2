"""Make the printable how-to guide for the Weather Display (3 letter pages, PDF).

  python docs/guide/make_guide.py [output folder]

Uses the real screens: a sample day drawn by generator/render.py and the Kindle
program's own menu/confirm/boot images, with numbered callouts. Pages are drawn
at 300 dpi with Pillow and packed into a PDF with PyMuPDF (fitz).
"""
import json
import os
import sys

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "generator"))
import render   # noqa: E402
import samples  # noqa: E402

DPI = 300
W, H = int(8.5 * DPI), 11 * DPI
M = 150                                   # page margin (0.5 in)
INK, GRAY, LIGHT, PANEL = (20, 20, 20), (95, 95, 95), (200, 200, 200), (242, 244, 246)
ACCENT, BEZEL = (25, 113, 194), (38, 38, 40)
IMG = os.path.join(ROOT, "kindle", "extensions", "closetdash", "img")
FONTS = os.path.join(ROOT, "generator", "fonts")
FILES = {"regular": "selawk.ttf", "bold": "selawkb.ttf", "semi": "selawksb.ttf", "light": "selawkl.ttf"}
MONO = r"C:\Windows\Fonts\consola.ttf"    # only for the Kindle's own text screens; falls back if missing
_f = {}


def font(size, weight="regular"):
    key = (size, weight)
    if key not in _f:
        if weight == "mono":
            path = MONO if os.path.exists(MONO) else os.path.join(FONTS, FILES["regular"])
        else:
            path = os.path.join(FONTS, FILES[weight])
        _f[key] = ImageFont.truetype(path, size)
    return _f[key]


def wrap(d, s, f, width):
    lines, line = [], ""
    for word in s.split():
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=f) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def para(d, x, y, s, f, width, lh=1.32, fill=INK):
    for line in wrap(d, s, f, width):
        d.text((x, y), line, font=f, fill=fill)
        y += int(f.size * lh)
    return y


def lead(d, x, y, bold, rest, width, size=42):
    """'Bold lead-in rest of the sentence', wrapping back to x."""
    fb, fr = font(size, "bold"), font(size)
    d.text((x, y), bold, font=fb, fill=INK)
    bw = d.textlength(bold + " ", font=fb)
    words, line, first, lh = rest.split(), "", True, int(size * 1.32)
    for word in words:
        avail = width - (bw if first else 0)
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=fr) <= avail or not line:
            line = trial
            continue
        d.text((x + (bw if first else 0), y), line, font=fr, fill=INK)
        y, line, first = y + lh, word, False
    d.text((x + (bw if first else 0), y), line, font=fr, fill=INK)
    return y + lh


def marker(d, cx, cy, n, r=34):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    d.text((cx, cy + 2), str(n), font=font(int(r * 1.25), "bold"), fill=(255, 255, 255), anchor="mm")


def device(screen, width, marks=(), pad=90):
    """Screen inside a Kindle-like bezel, scaled to `width`; marks = [(n, side, y_on_screen)]."""
    s = (width - 2 * pad) / screen.width
    sw, sh = round(screen.width * s), round(screen.height * s)
    top, bottom = pad, pad + 70
    dev = Image.new("RGB", (width, sh + top + bottom), (255, 255, 255))
    d = ImageDraw.Draw(dev)
    d.rounded_rectangle([0, 0, dev.width - 1, dev.height - 1], radius=70, fill=BEZEL)
    dev.paste(screen.convert("RGB").resize((sw, sh), Image.LANCZOS), (pad, top))
    d.text((dev.width / 2, top + sh + bottom / 2), "kindle", font=font(34, "semi"), fill=(150, 150, 150), anchor="mm")
    for n, side, y in marks:
        cx = pad / 2 if side == "left" else dev.width - pad / 2
        marker(d, cx, top + y * s, n, r=32)
    return dev


def note(d, x, y, n, title, body, width):
    marker(d, x + 34, y + 30, n)
    tx = x + 95
    d.text((tx, y), title, font=font(46, "bold"), fill=INK)
    return para(d, tx, y + 62, body, font(40), width - 95) + 34


def heading(d, y, title, sub=None):
    d.text((M, y), title, font=font(84, "bold"), fill=INK)
    y += 104
    if sub:
        y = para(d, M, y, sub, font(44, "light"), W - 2 * M, fill=GRAY)
    d.line([M, y + 18, W - M, y + 18], fill=INK, width=5)
    return y + 60


def subhead(d, y, title):
    d.text((M, y), title, font=font(58, "bold"), fill=ACCENT)
    return y + 82


def panel(img, box, fill=PANEL):
    ImageDraw.Draw(img).rounded_rectangle(box, radius=36, fill=fill)


def footer(d, n):
    d.text((W / 2, H - 90), f"Weather Display guide  ·  page {n} of 3", font=font(32), fill=GRAY, anchor="mm")


def kindle_text_screen(lines, size=(1072, 1448), row_h=78, start_row=2):
    """A screen like the ones the Kindle program writes with plain text (eips)."""
    im = Image.new("L", size, 255)
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        d.text((40, (start_row + i) * row_h), line, font=font(56, "mono"), fill=0)
    return im


def load_cfg():
    with open(os.path.join(ROOT, "generator", "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    with open(os.path.join(ROOT, "generator", "clothing_rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    return cfg, rules


# ------------------------------------------------------------------ page 1: reading the screen
def page1(cfg, rules):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    y = heading(d, M, "Your Weather Display",
                "Today's weather for Grand Rapids and what to wear, right on your Kindle. "
                "It updates by itself, so there's nothing to do but look.")
    day, _ = render.render(samples.sample("rainy_fall", "today"), rules, cfg)
    dev = device(day, 1150, [(1, "left", 80), (2, "right", 80), (3, "left", 380), (4, "left", 700),
                             (5, "left", 1010), (6, "left", 1395)])
    img.paste(dev, (M, y + 20))
    x, w, ny = M + 1150 + 80, W - M - (M + 1150 + 80), y + 30
    ny = note(d, x, ny, 1, "The day", "After 6 PM this switches to tomorrow and a black TOMORROW tag appears.", w)
    ny = note(d, x, ny, 2, "High and low", "The warmest and coldest temperatures of the day.", w)
    ny = note(d, x, ny, 3, "Morning, afternoon, evening",
              "A picture of the sky, the temperature, the chance of rain or snow, and what it "
              "actually feels like outside.", w)
    ny = note(d, x, ny, 4, "Temperature through the day",
              "From 6 AM to 10 PM. The dots mark the day's high and low.", w)
    ny = note(d, x, ny, 5, "What to wear",
              "Clothing ideas for the day. A small gray line explains why, for example when it "
              "feels colder than it looks.", w)
    note(d, x, ny, 6, "Sunrise, sunset, updated",
         "\"Updated\" is the time the forecast was made.", w)

    by = y + 20 + dev.height + 70
    panel(img, [M, by, W - M, by + 560])
    d.text((M + 60, by + 45), "It takes care of itself", font=font(54, "bold"), fill=INK)
    items = [("New forecast", "at 5:30 AM, noon and 6 PM."),
             ("Tomorrow", "shows from 6 PM on, so you can plan the next day the night before."),
             ("Light", "comes on from 5:30 to 8 AM, then turns off."),
             ("Keep it plugged in.", "That keeps it charged; there's no battery to look after.")]
    iy = by + 135
    for bold, rest in items:
        d.ellipse([M + 70, iy + 18, M + 88, iy + 36], fill=ACCENT)
        lead(d, M + 115, iy, bold, rest, W - 2 * M - 180)
        iy += 100

    ey = by + 560 + 70
    tom, _ = render.render(samples.sample("rainy_fall", "tomorrow"), rules, cfg)
    alert, _ = render.render(samples.sample("worst_case", "today"), rules, cfg)
    cw = (W - 2 * M - 80) // 2
    for i, (im, h, cap) in enumerate([(tom, 175, "After 6 PM: the TOMORROW tag"),
                                      (alert, 345, "Weather alerts appear in a black bar")]):
        crop = im.crop((0, 0, 1072, h)).convert("RGB")
        crop = crop.resize((cw, round(h * cw / 1072)), Image.LANCZOS)
        ImageDraw.Draw(crop).rectangle([0, 0, cw - 1, crop.height - 1], outline=LIGHT, width=4)
        ex = M + i * (cw + 80)
        img.paste(crop, (ex, ey))
        d.text((ex, ey + crop.height + 20), cap, font=font(38, "semi"), fill=GRAY)
    footer(d, 1)
    return img


# ------------------------------------------------------------------ page 2: the menu
def page2():
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    y = heading(d, M, "Tap the screen for the menu",
                "Tap anywhere on the weather. This menu appears and closes by itself after 15 seconds.")
    menu = Image.open(os.path.join(IMG, "menu.png"))
    dev = device(menu, 1050, [(1, "left", 417), (2, "left", 828), (3, "left", 1280), (4, "right", 1280)])
    img.paste(dev, (M, y + 20))
    x, w, ny = M + 1050 + 80, W - M - (M + 1050 + 80), y + 30
    ny = note(d, x, ny, 1, "Refresh now", "Gets the newest forecast right away.", w)
    ny = note(d, x, ny, 2, "Back to weather", "Closes the menu.", w)
    ny = note(d, x, ny, 3, "Device info",
              "Shows when the forecast last updated, the Wi-Fi status and the battery. "
              "Tap anywhere to go back.", w)
    ny = note(d, x, ny, 4, "Exit to Kindle",
              "Leaves the weather so you can read, shop or change settings. It asks first (below).", w)
    d.text((x, ny + 10), "(\"Closet Dash\" at the top is the program's name.)", font=font(36), fill=GRAY)

    by = y + 20 + dev.height + 80
    by = subhead(d, by, "Leaving the weather takes two taps")
    conf = Image.open(os.path.join(IMG, "confirm.png"))
    cdev = device(conf, 640, [(5, "left", 311), (6, "left", 900)], pad=70)
    img.paste(cdev, (M, by))
    x2, w2 = M + 640 + 70, 640
    ny = note(d, x2, by + 10, 5, "Yes, exit", "The small button in the top corner returns the normal Kindle.", w2)
    note(d, x2, ny, 6, "No", "The big button (or waiting 10 seconds) keeps the weather on.", w2)
    info = kindle_text_screen(["kindle-weather-2 v0.9", "", "Last good update:", "  Mon 12:00",
                               "Wi-Fi: CONNECTED", "Battery: 100%", "Failed tries: 0",
                               "Last problem: none", "", "Tap anywhere to", "go back."])
    idev = device(info, 640, pad=70)
    ix = W - M - 640
    img.paste(idev, (ix, by))
    d.text((ix + 320, by + idev.height + 30), "The Device info screen (simplified)", font=font(38, "semi"),
           fill=GRAY, anchor="ma")
    para(d, M, by + cdev.height + 40,
         "Why two taps? So little hands, or an accidental bump, can't switch the weather off.",
         font(40, "light"), 1400, fill=GRAY)
    footer(d, 2)
    return img


# ------------------------------------------------------------------ page 3: getting it back, Wi-Fi, help
def library_mock(width=1000):
    im = Image.new("RGB", (width, 520), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, width - 1, 519], radius=30, outline=LIGHT, width=4)
    d.text((40, 30), "Library", font=font(46, "bold"), fill=INK)
    rows = [("Start Weather", True), ("Your books", False), ("Your books", False)]
    for i, (title, hot) in enumerate(rows):
        ry = 120 + i * 130
        d.rectangle([40, ry, 120, ry + 100], fill=(225, 225, 225) if not hot else (60, 60, 60))
        d.text((150, ry + 50), title, font=font(42, "bold" if hot else "regular"),
               fill=INK if hot else (170, 170, 170), anchor="lm")
        if hot:
            d.rounded_rectangle([20, ry - 12, width - 20, ry + 112], radius=20, outline=ACCENT, width=6)
    return im


def page3(cfg, rules):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    y = heading(d, M, "Getting the weather back")
    lib = library_mock(1000)
    img.paste(lib, (M, y))
    ny = note(d, M, y + lib.height + 40, 1, "After reading or settings",
              "Go to your Library and tap Start Weather. The weather appears in about 10 seconds.", 1000)
    boot = Image.open(os.path.join(IMG, "boot.png"))
    bdev = device(boot, 560, pad=60)
    bx = W - M - 560 - 520
    img.paste(bdev, (bx + 520, y))
    note(d, bx - 40, y + 20, 2, "After a restart",
         "Nothing to do. About a minute after the Kindle starts, this countdown appears, then the weather. "
         "(Tapping during the countdown cancels it for that time.)", 540)
    y = max(ny, y + bdev.height) + 50

    y = subhead(d, y, "Joining your Wi-Fi")
    steps = ["Tap the weather, then EXIT TO KINDLE, then YES, EXIT.",
             "Tap the top of the screen and make sure Airplane Mode is off. Then open All Settings (the gear).",
             "Open the Wi-Fi settings, choose your network, type its password and tap Connect.",
             "Go to your Library and tap Start Weather."]
    for i, s in enumerate(steps, 1):
        marker(d, M + 34, y + 30, i)
        y = para(d, M + 95, y, s, font(42), W - 2 * M - 95) + 22
    y = para(d, M + 95, y, "The Kindle's menu names may look slightly different; the steps are the same.",
             font(36), W - 2 * M - 95, fill=GRAY) + 50

    y = subhead(d, y, "If something looks wrong")
    day, _ = render.render(samples.sample("calm_fifties", "today"), rules, cfg)
    crop = day.crop((0, 0, 1072, 252)).convert("RGB")
    cd = ImageDraw.Draw(crop)
    for i, line in enumerate(["Update failing since Mon 06:00 - check Wi-Fi",
                              "Still stuck? Hold the power button 40 sec", "Tap the screen for the menu."]):
        cd.rectangle([0, i * 50, 1072, i * 50 + 50], fill=(255, 255, 255))
        cd.text((12, i * 50 + 6), line, font=font(38, "mono"), fill=INK)
    cw = 1000
    crop = crop.resize((cw, round(crop.height * cw / 1072)), Image.LANCZOS)
    ImageDraw.Draw(crop).rectangle([0, 0, cw - 1, crop.height - 1], outline=LIGHT, width=4)
    img.paste(crop, (M, y))
    x, w = M + cw + 80, W - M - (M + cw + 80)
    para(d, x, y, "A message at the top means the Kindle couldn't get a new forecast. "
                  "The picture underneath may be out of date.", font(40), w)
    y += crop.height + 40
    tips = [("Check the Wi-Fi.", "Is the router on? It usually fixes itself within an hour once Wi-Fi is back."),
            ("Still stuck? Restart the Kindle.", "Hold the power button about 40 seconds until the screen "
             "goes blank, then let go. The weather comes back by itself."),
            ("\"Battery … please charge\"", "means the charger came unplugged."),
            ("Please don't", "install Amazon updates or reset the Kindle; that would remove the Weather Display.")]
    tw = W - 2 * M - 55 - 620
    ty = y
    for bold, rest in tips:
        d.ellipse([M + 10, y + 18, M + 28, y + 36], fill=ACCENT)
        y = lead(d, M + 55, y, bold, rest, tw) + 18
    calib = Image.open(os.path.join(IMG, "calib_1.png"))
    cdev = device(calib, 440, pad=50)
    img.paste(cdev, (W - M - 440, ty))
    para(d, W - M - 440, ty + cdev.height + 20,
         "If this Touch setup screen ever appears, tap each black dot (3 screens).", font(36), 440, fill=GRAY)
    footer(d, 3)
    return img


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else HERE
    os.makedirs(out, exist_ok=True)
    cfg, rules = load_cfg()
    pages = [page1(cfg, rules), page2(), page3(cfg, rules)]
    pdf = fitz.open()
    for i, pg in enumerate(pages, 1):
        png = os.path.join(out, f"guide_page{i}.png")
        pg.save(png, dpi=(DPI, DPI))
        p = pdf.new_page(width=612, height=792)
        p.insert_image(p.rect, filename=png)
    path = os.path.join(out, "Weather Display Guide.pdf")
    pdf.set_metadata({"title": "Weather Display Guide", "author": ""})
    pdf.save(path, deflate=True)
    print("wrote", path)


if __name__ == "__main__":
    main()
