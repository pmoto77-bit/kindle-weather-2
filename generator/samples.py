"""Made-up sample days (no network) for previews and self-tests.

synth_day() builds a smooth hourly curve from a few numbers so each sample stays short.
"""
import math

# window name -> hours it covers (for per-window codes / pops / feels gaps)
SPANS = {"night_am": range(0, 7), "morning": range(7, 12), "afternoon": range(12, 17),
         "evening": range(17, 23), "night_pm": range(23, 24)}


def _shape(h, peak=15):
    """0 at 6 AM, 1 at the peak hour, easing back to ~0.3 at midnight."""
    if 6 <= h <= peak:
        return 0.5 - 0.5 * math.cos(math.pi * (h - 6) / (peak - 6))
    if h > peak:
        return 0.3 + 0.7 * (0.5 + 0.5 * math.cos(math.pi * (h - peak) / (24 - peak)))
    return 0.3 * (6 - h) / 6


def _span(h):
    return next(k for k, r in SPANS.items() if h in r)


def synth_day(p):
    hours = []
    sr, ss = int(p.get("sunrise", "07:50")[:2]), int(p.get("sunset", "19:08")[:2])
    for h in range(24):
        sp = _span(h)
        t = round(p["lo"] + (p["hi"] - p["lo"]) * _shape(h, p.get("peak", 15)))
        gap = p.get("gap", {}).get(sp, 0)
        hours.append({
            "h": h, "temp": t, "feels": t - gap,
            "pop": p.get("pop", {}).get(sp, 0),
            "precip": 0.05 if p.get("pop", {}).get(sp, 0) >= 50 else 0.0,
            "snow": p.get("snow_in", 0) / 5 if sp == "morning" and p.get("snow_in") else 0.0,
            "code": p.get("code", {}).get(sp, 1),
            "wind": p.get("wind", 6), "gust": p.get("gust", 12), "wdir": p.get("wdir", 270),
            "uv": round(p.get("uv", 3) * max(0, math.sin(math.pi * (h - 7) / 12)), 1)
                  if 7 <= h <= 19 else 0,
            "is_day": sr <= h < ss})
    hi = max(x["temp"] for x in hours)
    lo = min(x["temp"] for x in hours)
    return {"date": p["date"], "label": p.get("label", "today"), "place": "Grand Rapids",
            "hi": hi, "lo": lo, "sunrise": p.get("sunrise", "07:50"),
            "sunset": p.get("sunset", "19:08"), "updated": "05:15", "hours": hours,
            "aqi": None if p.get("aqi") == "missing" else [p.get("aqi", 35)] * 24,
            "alerts": None if p.get("alerts") == "missing" else p.get("alerts", [])}


SAMPLES = {
    "rainy_fall": {
        "date": "2026-10-10", "lo": 41, "hi": 58, "wind": 12, "gust": 20, "wdir": 315, "uv": 3,
        "code": {"morning": 61, "afternoon": 3, "evening": 1, "night_am": 61},
        "pop": {"morning": 70, "afternoon": 30, "night_am": 60},
        "gap": {"morning": 5, "night_am": 5, "afternoon": 2, "evening": 3}},
    "cold_windy": {
        "date": "2026-11-18", "lo": 24, "hi": 36, "wind": 22, "gust": 35, "wdir": 315, "uv": 1,
        "sunrise": "07:35", "sunset": "17:15", "snow_in": 0.3,
        "code": {"morning": 71, "afternoon": 3, "evening": 0},
        "pop": {"morning": 50, "afternoon": 20},
        "gap": {"night_am": 11, "morning": 11, "afternoon": 10, "evening": 10}},
    "freezing_rain": {
        "date": "2027-01-14", "lo": 28, "hi": 36, "wind": 10, "gust": 18, "wdir": 180, "uv": 1,
        "sunrise": "08:13", "sunset": "17:31",
        "code": {"morning": 66, "afternoon": 61, "evening": 3},
        "pop": {"morning": 70, "afternoon": 60, "evening": 20},
        "gap": {"morning": 6, "afternoon": 5, "evening": 4}},
    "hot_humid": {
        "date": "2027-07-21", "lo": 72, "hi": 92, "wind": 8, "gust": 15, "wdir": 200, "uv": 9,
        "sunrise": "06:22", "sunset": "21:15", "aqi": 68,
        "code": {"morning": 1, "afternoon": 2, "evening": 95},
        "pop": {"evening": 55},
        "gap": {"morning": -3, "afternoon": -9, "evening": -6}},
    "big_swing": {
        "date": "2027-04-22", "lo": 34, "hi": 66, "wind": 6, "gust": 12, "uv": 6,
        "sunrise": "06:47", "sunset": "20:27",
        "code": {"morning": 0, "afternoon": 1, "evening": 0}},
    "smoke_day": {
        "date": "2027-06-08", "lo": 60, "hi": 78, "uv": 5, "aqi": 162,
        "sunrise": "06:09", "sunset": "21:20",
        "code": {"morning": 2, "afternoon": 2, "evening": 2}},
    "calm_fifties": {
        "date": "2026-10-23", "lo": 46, "hi": 55, "wind": 5, "gust": 10, "uv": 2,
        "code": {"morning": 3, "afternoon": 3, "evening": 3}},
    "winter_storm": {
        "date": "2026-12-05", "lo": 18, "hi": 27, "wind": 24, "gust": 40, "wdir": 340, "uv": 1,
        "sunrise": "08:02", "sunset": "17:08", "snow_in": 7,
        "code": {"morning": 75, "afternoon": 73, "evening": 71, "night_am": 73},
        "pop": {"morning": 90, "afternoon": 80, "evening": 60, "night_am": 80},
        "gap": {"night_am": 14, "morning": 14, "afternoon": 13, "evening": 13},
        "alerts": [{"event": "Winter Storm Warning", "severity": "Severe",
                    "ends": "2026-12-06T19:00"}]},
    "worst_case": {
        "date": "2027-02-02", "lo": 26, "hi": 38, "wind": 26, "gust": 44, "wdir": 250, "uv": 1,
        "aqi": 175, "snow_in": 3,
        "code": {"morning": 67, "afternoon": 63, "evening": 73},
        "pop": {"morning": 80, "afternoon": 70, "evening": 60},
        "gap": {"morning": 12, "afternoon": 9, "evening": 12},
        "alerts": [{"event": "Severe Thunderstorm Warning", "severity": "Severe",
                    "ends": "2027-02-02T18:45"},
                   {"event": "Winter Weather Advisory", "severity": "Moderate", "ends": None},
                   {"event": "Wind Advisory", "severity": "Moderate", "ends": None}]},
    "sources_down": {
        "date": "2026-10-12", "lo": 50, "hi": 63, "aqi": "missing", "alerts": "missing",
        "code": {"morning": 2, "afternoon": 1, "evening": 0}},
}


def sample(name, label="today"):
    return synth_day({**SAMPLES[name], "label": label})
