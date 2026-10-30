"""Holiday dates, and holiday art that never touches text or changes the forecast layout."""
import json
import os
import sys
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))

import holidays  # noqa: E402
import render    # noqa: E402
import samples   # noqa: E402


def load(name):
    with open(os.path.join(ROOT, "generator", name), encoding="utf-8") as f:
        return json.load(f)


CFG, RULES = load("config.json"), load("clothing_rules.json")


class TestHolidays(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(holidays.easter(2026), date(2026, 4, 5))
        self.assertEqual(holidays.easter(2027), date(2027, 3, 28))
        self.assertEqual(holidays.easter(2028), date(2028, 4, 16))
        self.assertEqual(holidays.holiday("2026-11-26"), "thanksgiving")
        self.assertEqual(holidays.holiday("2027-11-25"), "thanksgiving")
        self.assertEqual(holidays.holiday("2026-10-31"), "halloween")
        self.assertEqual(holidays.holiday("2026-12-25"), "christmas")
        self.assertIsNone(holidays.holiday("2026-10-30"))
        self.assertEqual(set(holidays.holidays(2027).values()), set(holidays.CAPTION))

    def test_every_holiday_has_art(self):
        for key in holidays.CAPTION:
            with self.subTest(holiday=key):
                im = render.holiday_image(key)
                self.assertIsNotNone(im)
                self.assertEqual(max(im.size), 400)

    def test_art_never_touches_text_or_changes_layout(self):
        for name in samples.SAMPLES:
            for key_date in ("2026-10-31", "2026-12-25", "2027-07-04"):
                with self.subTest(sample=name, date=key_date):
                    day = samples.sample(name)
                    plain = dict(day, date="2026-10-30")
                    _, a = render.render(plain, RULES, CFG)
                    _, b = render.render(dict(day, date=key_date), RULES, CFG)
                    self.assertIsNone(a["holiday"])
                    self.assertEqual((a["fit"], a["wear"]), (b["fit"], b["wear"]))
                    texts = [box for box, _ in b["boxes"]]
                    caption = [box for box, s in b["boxes"] if s == holidays.CAPTION[holidays.holiday(key_date)]]
                    if b["holiday"]:
                        self.assertEqual(len(caption), 1)
                        for box in texts:
                            if box is not caption[0]:
                                self.assertFalse(render._overlaps(caption[0], box, pad=0), name)


if __name__ == "__main__":
    unittest.main()
