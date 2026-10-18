"""Clothing rules: the right items, and reason lines only when a hidden driver applies."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))

import rules as R    # noqa: E402
import samples as S  # noqa: E402


def load(name):
    with open(os.path.join(ROOT, "generator", name), encoding="utf-8") as f:
        return json.load(f)


CFG, RULES = load("config.json"), load("clothing_rules.json")


def wear(name, **cfg_over):
    return R.wear_list(S.sample(name), RULES, {**CFG, **cfg_over})


def by_key(items):
    return {i["key"]: i for i in items}


class TestSampleDays(unittest.TestCase):
    def test_rainy_fall(self):
        w = by_key(wear("rainy_fall"))
        self.assertTrue(w["main"]["text"].startswith("Warm jacket; shed it by"))
        self.assertIn("feels like", w["main"]["reason"])
        self.assertEqual(w["rain"]["text"], "Rain jacket for the morning")
        self.assertIsNone(w["rain"]["reason"])  # timing is already in the item text

    def test_cold_windy(self):
        w = by_key(wear("cold_windy"))
        self.assertIn("feels like", w["main"]["reason"])
        self.assertEqual(w["wind"]["reason"], "NW gusts to 35 mph")
        self.assertNotIn("shed", w["main"]["text"])  # never 'shed' a winter coat

    def test_freezing_rain(self):
        w = by_key(wear("freezing_rain"))
        self.assertEqual(w["ice"]["text"], "Boots with good grip")
        self.assertTrue(w["ice"]["reason"].startswith("freezing rain around"))
        self.assertEqual(w["rain"]["text"], "Rain jacket for the afternoon")

    def test_hot_humid(self):
        w = by_key(wear("hot_humid"))
        self.assertEqual(w["main"]["trigger"], "heat")
        self.assertTrue(w["rain"]["reason"].startswith("thunderstorms around"))
        self.assertEqual(w["legs"]["text"], "Shorts weather")

    def test_big_swing(self):
        w = by_key(wear("big_swing"))
        self.assertIn("shed it by", w["main"]["text"])
        self.assertTrue(w["main"]["reason"].startswith("warms up"))
        self.assertIn("evening", w)  # layer was shed, so remind for after dark

    def test_smoke_day(self):
        items = wear("smoke_day")
        self.assertEqual(items[0]["key"], "aqi")
        self.assertIn("162", items[0]["reason"])

    def test_calm_day_has_no_reasons(self):
        self.assertEqual([i["reason"] for i in wear("calm_fifties") if i["reason"]], [])

    def test_no_duplicate_footwear(self):
        keys = [i["key"] for i in wear("worst_case")]
        self.assertIn("ice", keys)
        self.assertNotIn("snow", keys)

    def test_caps(self):
        for name in S.SAMPLES:
            items = wear(name)
            self.assertLessEqual(len(items), RULES["max_items"], name)
            self.assertLessEqual(sum(1 for i in items if i["reason"]), RULES["max_reasons"], name)
            for i in items:  # a reason always names its trigger
                self.assertEqual(bool(i["reason"]), bool(i["trigger"]), (name, i))


class TestComfortOffset(unittest.TestCase):
    def band(self, items):
        main = by_key(items)["main"]["text"].split(";")[0]
        return [b["wear"] for b in RULES["warmth_bands"]].index(main)

    def test_runs_cold_suggests_warmer(self):
        normal = self.band(wear("calm_fifties"))
        cold = self.band(wear("calm_fifties", comfort_offset_f=5))
        self.assertLess(cold, normal)

    def test_runs_warm_suggests_lighter(self):
        normal = self.band(wear("rainy_fall"))
        warm = self.band(wear("rainy_fall", comfort_offset_f=-10))
        self.assertGreater(warm, normal)


class TestHelpers(unittest.TestCase):
    def test_clock_and_compass(self):
        self.assertEqual([R.clock(h) for h in (0, 7, 12, 15)], ["12 AM", "7 AM", "noon", "3 PM"])
        self.assertEqual([R.compass(d) for d in (0, 92, 315, 359)], ["N", "E", "NW", "N"])

    def test_aqi_line(self):
        self.assertIsNone(R.aqi_line({"aqi": [40] * 24}, RULES))
        self.assertEqual(R.aqi_line({"aqi": [68] * 24}, RULES), "Air quality: Moderate (68)")
        self.assertIsNone(R.aqi_line({"aqi": None}, RULES))


if __name__ == "__main__":
    unittest.main()
