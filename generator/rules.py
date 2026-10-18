"""Turn a day dict into the WHAT TO WEAR list, using clothing_rules.json.

Each item: {"key", "text", "reason" (str|None), "trigger" (str|None)}.
A reason is attached only when a hidden driver changed the choice
(feels-like gap, wind, big swing, UV, timing, heat, ice, AQI).
"""

PRECIP_RANK = {"storm": 4, "ice": 3, "snow": 2, "rain": 1}


def category(code):
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (56, 57, 66, 67):
        return "ice"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    if 51 <= code <= 82:
        return "rain"
    return "cloud"


def clock(h):
    """7 -> '7 AM', 15 -> '3 PM', 12 -> 'noon'."""
    if h == 12:
        return "noon"
    return f"{(h - 1) % 12 + 1} {'AM' if h < 12 else 'PM'}"


def compass(deg):
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((deg % 360) / 45 + 0.5) % 8]


def band_index(bands, t):
    for i, b in enumerate(bands):
        if t < b["below"]:
            return i
    return len(bands) - 1


def _hours(day, start, end):
    return [x for x in day["hours"] if start <= x["h"] <= end]


def wear_list(day, rules, cfg):
    t = rules["triggers"]
    say, why = rules["items"], rules["reasons"]
    bands = rules["warmth_bands"]
    off = cfg.get("comfort_offset_f", 0)
    win = {w["key"]: w for w in cfg["windows"]}

    def dress(x):  # temperature used for clothing decisions
        return x["feels"] - off

    def hrs(key):
        return _hours(day, win[key]["start"], win[key]["end"])

    daytime = _hours(day, win["morning"]["start"], win["evening"]["end"])
    items = {}

    # --- AQI
    aqi = [v for v in (day.get("aqi") or [])[7:23] if v is not None]
    if aqi and max(aqi) >= t["aqi_item"]:
        items["aqi"] = (say["aqi"], why["aqi"].format(aqi=max(aqi)), "aqi")

    # --- ice
    ice = [x for x in daytime if category(x["code"]) == "ice" and x["pop"] >= t["ice_pop"]]
    if ice:
        items["ice"] = (say["ice"], why["ice"].format(time=clock(ice[0]["h"])), "ice")

    # --- main warmth item (or heat)
    morning, afternoon, evening = hrs("morning"), hrs("afternoon"), hrs("evening")
    cold = min(morning, key=dress)
    warm = max(afternoon, key=dress)
    hot = max(daytime, key=lambda x: x["feels"])
    if hot["feels"] - off >= t["heat"]:
        items["main"] = (say["heat"], why["heat"].format(feels=hot["feels"], time=clock(hot["h"])), "heat")
    else:
        bi_m = band_index(bands, dress(cold))
        bi_a = band_index(bands, dress(warm))
        text = bands[bi_m]["wear"]
        swing = max(x["temp"] for x in afternoon) - min(x["temp"] for x in morning)
        shed = bi_a > bi_m and swing >= t["shed_swing"] and dress(warm) >= t["shed_min_afternoon"]
        if shed:
            limit = bands[bi_m]["below"]
            first = next((x["h"] for x in _hours(day, 8, 17) if dress(x) >= limit), 14)
            when = next(v for k, v in sorted(rules["shed_words"].items(), key=lambda kv: int(kv[0]))
                        if first <= int(k))
            text = say["shed"].format(wear=text, when=when)
        reason = trig = None
        if cold["temp"] - cold["feels"] >= t["feels_gap"]:
            reason, trig = why["feels"].format(feels=cold["feels"], time=clock(cold["h"])), "feels"
        elif swing >= t["swing"]:
            reason, trig = why["swing"].format(n=swing), "swing"
        items["main"] = (text, reason, trig)

        # evening reminder: only if a layer was shed, or the evening is colder than the morning
        bi_e = band_index(bands, min(dress(x) for x in evening))
        if bands[bi_e].get("evening") and ((shed and bi_e < bi_a) or bi_e < bi_m):
            items["evening"] = (bands[bi_e]["evening"], None, None)

    # --- wind (computed early: it changes the rain wording)
    windy = [x for x in daytime if x["gust"] >= t["gust_mph"] or x["wind"] >= t["wind_mph"]]
    gusty = max(daytime, key=lambda x: x["gust"])
    wind_reason = why["wind"].format(dir=compass(gusty["wdir"]), gust=gusty["gust"])

    # --- rain / storms
    def is_wet(x):
        c = category(x["code"])
        return c in ("rain", "storm") or (c not in ("snow", "ice") and x["temp"] > 34)

    rain = [x for x in daytime if x["pop"] >= t["rain_pop"] and is_wet(x)]
    if rain:
        touched = [k for k in ("morning", "afternoon", "evening")
                   if any(win[k]["start"] <= x["h"] <= win[k]["end"] for x in rain)]
        storm = [x for x in rain if category(x["code"]) == "storm"]
        if windy and any(x in windy for x in rain):
            items["rain"] = (say["rain_windy"], wind_reason, "wind")
        elif len(touched) == 1:
            text = say["rain_window"].format(window=rules["window_words"][touched[0]])
            reason = why["storm"].format(time=clock(storm[0]["h"])) if storm else None
            items["rain"] = (text, reason, "timing" if reason else None)
        else:
            reason = None
            if storm:
                reason = why["storm"].format(time=clock(storm[0]["h"]))
            elif rain[0]["h"] >= 10:
                reason = why["rain_start"].format(time=clock(rain[0]["h"]))
            items["rain"] = (say["rain_all_day"], reason, "timing" if reason else None)
    elif any(x["pop"] >= t["maybe_pop"] and is_wet(x) for x in daytime):
        items["rain"] = (say["rain_maybe"], None, None)

    # --- snow
    snow = [x for x in daytime if category(x["code"]) == "snow" and x["pop"] >= t["snow_pop"]]
    if snow:
        total = round(sum(x["snow"] for x in day["hours"]), 1)
        if total >= t["deep_snow_in"]:
            items["snow"] = (say["snow_deep"], why["snow_amount"].format(inches=f"{total:g}"), "timing")
        else:
            items["snow"] = (say["snow"], None, None)
        if "ice" in items:  # one footwear item, not two
            deep = total >= t["deep_snow_in"]
            items["ice"] = (say["snow_ice"] if deep else say["ice"],) + items["ice"][1:]
            del items["snow"]

    # --- wind layer (only when it isn't warm, and not already covered by the rain item)
    if windy and max(dress(x) for x in daytime) < 65 and items.get("rain", (None,))[0] != say["rain_windy"]:
        items["wind"] = (say["wind"], wind_reason, "wind")

    # --- UV
    uv = max(daytime, key=lambda x: x["uv"])
    if uv["uv"] >= t["uv"]:
        items["uv"] = (say["uv"], why["uv"].format(uv=int(round(uv["uv"])), time=clock(uv["h"])), "uv")

    # --- legs and shoes
    top = max(dress(x) for x in _hours(day, 7, 17))
    if top >= t["legs_warm_from"] and min(dress(x) for x in morning) >= t["legs_warm_morning_min"]:
        items["legs"] = (say["legs_warm"], None, None)
    elif top < t["legs_cool_below"] or snow or ice:
        items["legs"] = (say["legs_cool"], None, None)

    # --- order, cap items, cap reasons
    order = rules["item_priority"]
    keys = sorted(items, key=order.index)[: rules["max_items"]]
    out = [{"key": k, "text": items[k][0], "reason": items[k][1], "trigger": items[k][2]} for k in keys]
    trim_reasons(out, rules, rules["max_reasons"])
    return out


def trim_reasons(items, rules, keep):
    """Drop reasons (lowest priority first) until at most `keep` remain. Returns dropped triggers."""
    pri = rules["reason_priority"]
    dropped = []
    while sum(1 for i in items if i["reason"]) > keep:
        victim = max((i for i in items if i["reason"]), key=lambda i: pri.index(i["trigger"]))
        dropped.append(victim["trigger"])
        victim["reason"] = victim["trigger"] = None
    return dropped


def aqi_line(day, rules):
    """'Air quality: Moderate (68)' when AQI is at or above the line threshold, else None."""
    vals = [v for v in (day.get("aqi") or [])[7:23] if v is not None]
    if not vals or max(vals) < rules["triggers"]["aqi_line"]:
        return None
    a = max(vals)
    name = ("Moderate" if a <= 100 else "Unhealthy for sensitive groups" if a <= 150
            else "Unhealthy" if a <= 200 else "Very unhealthy" if a <= 300 else "Hazardous")
    return f"Air quality: {name} ({a})"
