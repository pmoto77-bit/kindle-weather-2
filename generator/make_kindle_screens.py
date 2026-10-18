"""Draw the Kindle program's own screens (menu, confirm, touch calibration, boot countdown).

  python generator/make_kindle_screens.py

Writes grayscale PNGs at the screen size in config.json to kindle/extensions/closetdash/img/
plus img/buttons.txt, which holds every tap target ("screen name x0 y0 x1 y1") and
calibration dot ("calib n x y") in screen pixels - the single source of truth for
dash.sh's hit-testing. Layout is in PW1 pixels (758x1024), scaled like the weather picture.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from render import BLACK, DARK, M, MID, WHITE, Canvas, font, screen  # noqa: E402

with open(os.path.join(HERE, "config.json"), encoding="utf-8") as _f:
    W, H, S = screen(json.load(_f))
OUT = os.path.join(os.path.dirname(HERE), "kindle", "extensions", "closetdash", "img")

# tap targets: screen -> [(name, (x0, y0, x1, y1), label, sublabel, style)]
BUTTONS = {
    "menu": [
        ("refresh", (M, 170, W - M, 420), "REFRESH NOW", "get the latest forecast", "big"),
        ("back", (M, 460, W - M, 710), "BACK TO WEATHER", None, "big"),
        ("info", (M, 830, M + 300, 980), "DEVICE INFO", None, "small"),
        ("exit", (W - M - 300, 830, W - M, 980), "EXIT TO KINDLE", None, "small"),
    ],
    "confirm": [
        ("yes", (M, 150, M + 300, 290), "YES, EXIT", None, "small"),
        ("no", (M, 340, W - M, 980), "NO", "keep showing the weather", "big"),
    ],
}
CALIB = [(1, 60, 60, "top-left"), (2, W - 60, 60, "top-right"), (3, 60, H - 60, "bottom-left")]


def canvas():
    c = Canvas(W, H, S)
    return c.img, c.d


def centered(d, y, text, f, fill=BLACK):
    d.text((W / 2, y), text, font=f, fill=fill, anchor="ma")


def button(d, box, label, sub, style):
    x0, y0, x1, y1 = box
    if style == "big":
        d.rounded_rectangle(box, radius=24, outline=BLACK, width=6, fill=WHITE)
        size, cy = 52, (y0 + y1) / 2 - (22 if sub else 0)
    else:
        d.rounded_rectangle(box, radius=18, outline=BLACK, width=4, fill=235)
        size, cy = 30, (y0 + y1) / 2
    d.text(((x0 + x1) / 2, cy), label, font=font(size, "bold"), fill=BLACK, anchor="mm")
    if sub:
        d.text(((x0 + x1) / 2, cy + 50), sub, font=font(26), fill=MID, anchor="mm")


def save(img, name):
    img.point(lambda v: (v // 17) * 17).save(os.path.join(OUT, name), optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)

    img, d = canvas()
    centered(d, 50, "Closet Dash", font(44, "bold"))
    centered(d, 108, "Closes by itself in 15 seconds", font(26), MID)
    for _, box, label, sub, style in BUTTONS["menu"]:
        button(d, box, label, sub, style)
    save(img, "menu.png")

    img, d = canvas()
    d.text((M + 340, 190), "Exit to the Kindle?", font=font(34, "bold"), fill=BLACK, anchor="lm")
    d.text((M + 340, 240), "Closes by itself in 10 s", font=font(24), fill=MID, anchor="lm")
    for _, box, label, sub, style in BUTTONS["confirm"]:
        button(d, box, label, sub, style)
    save(img, "confirm.png")

    for n, x, y, where in CALIB:
        img, d = canvas()
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=BLACK)
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=WHITE)
        centered(d, 380, "Touch setup", font(48, "bold"))
        centered(d, 450, f"Tap the black dot ({where})", font(34))
        centered(d, 500, f"Step {n} of 3", font(28), MID)
        centered(d, 620, "This happens once, so the menu", font(26), DARK)
        centered(d, 656, "buttons know where you tap.", font(26), DARK)
        save(img, f"calib_{n}.png")

    img, d = canvas()
    centered(d, 330, "Closet Dash", font(48, "bold"))
    centered(d, 400, "starts in about a minute.", font(34))
    centered(d, 560, "Tap anywhere to cancel", font(34, "bold"))
    centered(d, 606, "and go back to the Kindle.", font(34, "bold"))
    save(img, "boot.png")

    with open(os.path.join(OUT, "buttons.txt"), "w", encoding="ascii", newline="\n") as f:
        f.write(f"# screen name x0 y0 x1 y1 in screen pixels ({round(W * S)}x{round(H * S)}; "
                "made by generator/make_kindle_screens.py)\n")
        for page, items in BUTTONS.items():
            for name, box, *_ in items:
                f.write(f"{page} {name} {' '.join(str(round(v * S)) for v in box)}\n")
        for n, x, y, _ in CALIB:
            f.write(f"calib {n} {round(x * S)} {round(y * S)}\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
