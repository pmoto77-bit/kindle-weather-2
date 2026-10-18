"""Every sample renders inside the screen, above the footer, with no overlapping text,
and the PW3 scaling changes nothing but the pixel count."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))

from PIL import Image, ImageChops  # noqa: E402

import render   # noqa: E402
import samples  # noqa: E402


def load(name):
    with open(os.path.join(ROOT, "generator", name), encoding="utf-8") as f:
        return json.load(f)


CFG, RULES = load("config.json"), load("clothing_rules.json")
PW, PH = CFG["screen"]["width"], CFG["screen"]["height"]   # image pixels
W, H, S = render.screen(CFG)                                # layout units (PW1 pixels)
PW1 = {**CFG, "screen": {"width": 758, "height": 1024}}


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class TestFit(unittest.TestCase):
    def check(self, name, label):
        img, info = render.render(samples.sample(name, label), RULES, CFG)
        tag = f"{name}/{label}"
        self.assertEqual((img.size, img.mode), ((PW, PH), "L"), tag)
        self.assertLessEqual(info["bottom"], H - render.FOOTER_H - 10, tag)
        boxes = info["boxes"]
        for (b, s) in boxes:
            self.assertTrue(0 <= b[0] and b[2] <= W and 0 <= b[1] and b[3] <= H, f"{tag}: '{s}' off screen")
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                self.assertFalse(overlaps(boxes[i][0], boxes[j][0]),
                                 f"{tag}: '{boxes[i][1]}' overlaps '{boxes[j][1]}'")
        return info

    def test_all_samples_today_and_tomorrow(self):
        for name in samples.SAMPLES:
            for label in ("today", "tomorrow"):
                with self.subTest(sample=name, label=label):
                    self.check(name, label)

    def test_worst_case_keeps_banner_and_aqi(self):
        for label in ("today", "tomorrow"):
            info = self.check("worst_case", label)
            self.assertTrue(info["banner"].startswith("SEVERE THUNDERSTORM WARNING"))
            self.assertIn("+2 more", info["banner"])
            self.assertEqual(info["aqi_line"], "Air quality: Unhealthy (175)")

    def test_normal_day_needs_no_fit_steps(self):
        self.assertEqual(self.check("rainy_fall", "today")["fit"], [])
        self.assertEqual(self.check("cold_windy", "today")["fit"], [])

    def test_missing_sources_are_flagged(self):
        info = self.check("sources_down", "today")
        texts = [s for _, s in info["boxes"]]
        self.assertIn("Weather alerts and air quality unavailable this update", texts)

    def test_curve_labels_high_and_low(self):
        texts = [s for _, s in self.check("big_swing", "today")["boxes"]]
        self.assertIn("66°", texts)
        self.assertIn("34°", texts)
        flat = samples.sample("calm_fifties")
        for x in flat["hours"]:
            x["temp"] = 50
        c = render.Canvas(W, H)
        render.draw_curve(c, 0, flat, CFG, 90)
        self.assertEqual([s for _, s in c.boxes].count("50°"), 1)

    def test_scaling_fits_like_pw1(self):
        for name in samples.SAMPLES:
            for label in ("today", "tomorrow"):
                with self.subTest(sample=name, label=label):
                    day = samples.sample(name, label)
                    _, a = render.render(day, RULES, PW1)
                    _, b = render.render(day, RULES, CFG)
                    self.assertEqual((a["fit"], a["wear"]), (b["fit"], b["wear"]))

    def test_pw1_size_matches_original_renderer(self):
        # golden image made by the closet-kindle renderer before scaling was added
        img, _ = render.render(samples.sample("worst_case"), RULES, PW1)
        gold = Image.open(os.path.join(ROOT, "tests", "fixtures", "golden_worst_case_758.png"))
        self.assertIsNone(ImageChops.difference(img, gold.convert("L")).getbbox())

    def test_kindle_buttons_match_screen(self):
        # img/buttons.txt must be regenerated (make_kindle_screens.py) whenever the screen changes
        path = os.path.join(ROOT, "kindle", "extensions", "closetdash", "img", "buttons.txt")
        with open(path, encoding="ascii") as f:
            rows = [line.split() for line in f if not line.startswith("#")]
        calib = {r[1]: (int(r[2]), int(r[3])) for r in rows if r[0] == "calib"}
        self.assertEqual(calib["2"], (round((W - 60) * S), round(60 * S)))
        for r in rows:
            vals = [int(v) for v in r[2:]]
            self.assertTrue(all(0 <= v <= PW for v in vals[0::2]) and all(0 <= v <= PH for v in vals[1::2]), r)
        for name in ("menu", "confirm", "calib_1", "boot"):
            img = Image.open(os.path.join(os.path.dirname(path), name + ".png"))
            self.assertEqual(img.size, (PW, PH), name)

    def test_banner_end_time_wording(self):
        day = samples.sample("winter_storm")
        self.assertEqual(render.banner_text(day), "WINTER STORM WARNING until 7 PM Sun")


if __name__ == "__main__":
    unittest.main()
