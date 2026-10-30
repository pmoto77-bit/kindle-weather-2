"""Prepare holiday art for the e-ink screen from OpenMoji "black" PNG downloads.

  python generator/make_holiday_art.py <folder with OpenMoji *_black.png files>

For each holiday it flattens the transparent PNG onto white, converts it to grayscale,
trims the empty border and saves generator/holiday_art/<holiday>.png (at most 400 px,
so the build can shrink it smoothly to any size). Run once, when the art changes; the
cloud build only reads the results.

OpenMoji (https://openmoji.org/) - CC BY-SA 4.0. Changes: flattened onto white,
converted to grayscale, trimmed and resized. See generator/holiday_art/LICENSE.txt.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "holiday_art")
SOURCES = {   # holiday -> OpenMoji hexcode (file <hexcode>_black.png)
    "new_year": "1F386",       # fireworks
    "valentine": "1F495",      # two hearts
    "st_patrick": "2618",      # shamrock
    "easter": "271D",          # latin cross
    "july4": "1F5FD",          # Statue of Liberty
    "halloween": "1F383",      # jack-o-lantern
    "thanksgiving": "1F983",   # turkey
    "christmas": "1F384",      # Christmas tree
}


def prepare(src):
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
    flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    flat.alpha_composite(rgba)
    gray = flat.convert("L")
    box = rgba.getchannel("A").getbbox()
    gray = gray.crop(box)
    gray.thumbnail((400, 400), Image.LANCZOS)
    return gray


def main(folder):
    os.makedirs(OUT, exist_ok=True)
    for key, code in SOURCES.items():
        src = os.path.join(folder, f"{code}_black.png")
        if not os.path.exists(src):
            print(f"missing {key}: {src} (keeps the drawn fallback)")
            continue
        art = prepare(src)
        art.save(os.path.join(OUT, f"{key}.png"), optimize=True)
        print(f"{key:13} {code:6} -> {art.size}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
