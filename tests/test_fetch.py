"""Parsing real API responses (captured 2026-10-10 for Grand Rapids) into day dicts."""
import json
import os
import sys
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))

import fetch  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


CFG = load(os.path.join(ROOT, "generator", "config.json"))
FORECAST = load(os.path.join(FIX, "openmeteo_forecast.json"))
AQI = load(os.path.join(FIX, "openmeteo_aqi.json"))
NOW = datetime(2026, 10, 10, 5, 15)


def alert(event, onset, ends, status="Actual", mtype="Alert"):
    return {"properties": {"event": event, "severity": "Severe", "status": status,
                           "messageType": mtype, "onset": onset, "ends": ends}}


class TestBuildDays(unittest.TestCase):
    def test_two_full_days(self):
        days = fetch.build_days(CFG, FORECAST, AQI, {"features": []}, NOW)
        self.assertEqual([d["date"] for d in days], ["2026-10-10", "2026-10-11"])
        self.assertEqual([d["label"] for d in days], ["today", "tomorrow"])
        for d in days:
            self.assertEqual([x["h"] for x in d["hours"]], list(range(24)))
            self.assertTrue(all(isinstance(x["temp"], int) for x in d["hours"]))
            self.assertLessEqual(d["lo"], d["hi"])
            self.assertEqual(len(d["aqi"]), 24)
            self.assertEqual(d["alerts"], [])
            self.assertRegex(d["sunrise"], r"^\d\d:\d\d$")
        self.assertEqual(days[0]["updated"], "05:15")

    def test_missing_sources_become_none(self):
        today = fetch.build_days(CFG, FORECAST, None, None, NOW)[0]
        self.assertIsNone(today["aqi"])
        self.assertIsNone(today["alerts"])

    def test_alert_filtering_and_local_time(self):
        alerts = {"features": [
            alert("Winter Storm Warning", "2026-10-10T22:00:00-04:00", "2026-10-11T23:00:00Z"),
            alert("Test Message", "2026-10-10T06:00:00-04:00", "2026-10-10T20:00:00-04:00", status="Test"),
            alert("Wind Advisory", "2026-10-10T06:00:00-04:00", "2026-10-10T20:00:00-04:00", mtype="Cancel"),
            alert("Frost Advisory", "2026-10-09T01:00:00-04:00", "2026-10-09T09:00:00-04:00"),
        ]}
        today, tomorrow = fetch.build_days(CFG, FORECAST, AQI, alerts, NOW)
        self.assertEqual([a["event"] for a in today["alerts"]], ["Winter Storm Warning"])
        self.assertEqual(today["alerts"][0]["ends"], "2026-10-11T19:00")  # 23:00Z -> 7 PM EDT
        self.assertEqual([a["event"] for a in tomorrow["alerts"]], ["Winter Storm Warning"])


if __name__ == "__main__":
    unittest.main()
