"""Download the forecast, air quality and NWS alerts, and turn them into 'day' dicts.

A day dict is what rules.py and render.py work from:
  {"date": "2026-10-10", "label": "today"|"tomorrow", "place": "...",
   "hi": 58, "lo": 41, "sunrise": "07:53", "sunset": "19:07", "updated": "05:15",
   "hours": [24 x {"h", "temp", "feels", "pop", "precip", "snow", "code",
                   "wind", "gust", "wdir", "uv", "is_day"}],
   "aqi": [24 ints/None] or None (unavailable),
   "alerts": [{"event", "severity", "ends"}] or None (unavailable)}
Times are local (naive) strings; Open-Meteo returns them in the configured time zone.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
ALERTS_URL = "https://api.weather.gov/alerts/active"

HOURLY = ("temperature_2m,apparent_temperature,precipitation_probability,precipitation,"
          "snowfall,weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
          "uv_index,is_day")
DAILY = "temperature_2m_max,temperature_2m_min,sunrise,sunset"


def get_json(url, params, headers=None, tries=3):
    full = url + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(full, headers=headers or {})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # network hiccup: retry, then give up loudly
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"Could not download {url}: {last}")


def fetch_all(cfg):
    """Return (forecast, aqi, alerts, sources). Forecast failure raises; the others degrade."""
    loc = {"latitude": cfg["latitude"], "longitude": cfg["longitude"]}
    ua = {"User-Agent": cfg["user_agent"]}
    forecast = get_json(FORECAST_URL, {
        **loc, "hourly": HOURLY, "daily": DAILY, "timezone": cfg["timezone"],
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "precipitation_unit": "inch", "forecast_days": 3}, ua)
    sources = {"forecast": "ok"}
    try:
        aqi = get_json(AQI_URL, {**loc, "hourly": "us_aqi", "timezone": cfg["timezone"],
                                 "forecast_days": 3}, ua)
        sources["aqi"] = "ok"
    except RuntimeError:
        aqi, sources["aqi"] = None, "unavailable"
    try:
        alerts = get_json(ALERTS_URL, {"point": f"{cfg['latitude']},{cfg['longitude']}"},
                          {**ua, "Accept": "application/geo+json"})
        sources["alerts"] = "ok"
    except RuntimeError:
        alerts, sources["alerts"] = None, "unavailable"
    return forecast, aqi, alerts, sources


def local_now(forecast):
    """Current local time, using the UTC offset Open-Meteo reports for the location."""
    off = timedelta(seconds=forecast.get("utc_offset_seconds", 0))
    return (datetime.now(timezone.utc) + off).replace(tzinfo=None)


def _r(v):
    return None if v is None else int(round(v))


def _alerts_for(alerts_json, day_start, offset_s):
    """Active, real alerts that overlap the given local day."""
    if alerts_json is None:
        return None
    tz = timezone(timedelta(seconds=offset_s))
    day_end = day_start + timedelta(days=1)
    out = []
    for f in alerts_json.get("features", []):
        p = f.get("properties", {})
        if p.get("status") != "Actual" or p.get("messageType") == "Cancel":
            continue

        def loc(s):
            return datetime.fromisoformat(s).astimezone(tz).replace(tzinfo=None) if s else None

        start = loc(p.get("onset") or p.get("effective"))
        end = loc(p.get("ends") or p.get("expires"))
        if (start and start >= day_end) or (end and end <= day_start):
            continue
        out.append({"event": p.get("event", "Weather alert"),
                    "severity": p.get("severity", "Unknown"),
                    "ends": end.isoformat(timespec="minutes") if end else None})
    return out


def build_days(cfg, forecast, aqi, alerts, now=None):
    """Return [today, tomorrow] day dicts from raw API responses."""
    now = now or local_now(forecast)
    offset = forecast.get("utc_offset_seconds", 0)
    hourly, daily = forecast["hourly"], forecast["daily"]
    index = {t: i for i, t in enumerate(hourly["time"])}
    aqi_index = {}
    if aqi is not None:
        aqi_index = {t: v for t, v in zip(aqi["hourly"]["time"], aqi["hourly"]["us_aqi"])}

    days = []
    for n, label in enumerate(("today", "tomorrow")):
        d = (now + timedelta(days=n)).date()
        ds = d.isoformat()
        di = daily["time"].index(ds)
        hours = []
        for h in range(24):
            i = index[f"{ds}T{h:02d}:00"]
            g = lambda k: hourly[k][i]  # noqa: E731
            hours.append({
                "h": h, "temp": _r(g("temperature_2m")), "feels": _r(g("apparent_temperature")),
                "pop": _r(g("precipitation_probability")) or 0,
                "precip": g("precipitation") or 0.0, "snow": g("snowfall") or 0.0,
                "code": g("weather_code") or 0, "wind": _r(g("wind_speed_10m")) or 0,
                "gust": _r(g("wind_gusts_10m")) or 0, "wdir": g("wind_direction_10m") or 0,
                "uv": round(g("uv_index") or 0, 1), "is_day": bool(g("is_day"))})
        days.append({
            "date": ds, "label": label, "place": cfg["place"],
            "hi": _r(daily["temperature_2m_max"][di]), "lo": _r(daily["temperature_2m_min"][di]),
            "sunrise": daily["sunrise"][di][11:16], "sunset": daily["sunset"][di][11:16],
            "updated": now.strftime("%H:%M"),
            "hours": hours,
            "aqi": None if aqi is None else [_r(aqi_index.get(f"{ds}T{h:02d}:00")) for h in range(24)],
            "alerts": _alerts_for(alerts, datetime(d.year, d.month, d.day), offset),
        })
    return days
