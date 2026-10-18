"""Build the closet Kindle images.

  python generator/make_dashboard.py --out site                  live: today.png, tomorrow.png, status.json/txt
  python generator/make_dashboard.py --sample all --out preview   every made-up sample day, no network
  python generator/make_dashboard.py --sample cold_windy         one sample
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fetch    # noqa: E402
import render   # noqa: E402
import samples  # noqa: E402


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def build_samples(names, out, cfg, rules):
    for n in names:
        labels = ("today", "tomorrow") if n == "rainy_fall" else ("today",)
        for label in labels:
            img, info = render.render(samples.sample(n, label), rules, cfg)
            path = os.path.join(out, f"{n}{'' if label == 'today' else '_tomorrow'}.png")
            img.save(path, optimize=True)
            fit = f"  fit: {', '.join(info['fit'])}" if info["fit"] else ""
            print(f"{os.path.basename(path):28} {' | '.join(info['wear'])}{fit}")


def build_live(out, cfg, rules, history):
    forecast, aqi, alerts, sources = fetch.fetch_all(cfg)
    now = fetch.local_now(forecast)
    days = fetch.build_days(cfg, forecast, aqi, alerts, now)
    status = {"built": now.isoformat(timespec="minutes"), "place": cfg["place"],
              "utc_offset_seconds": forecast.get("utc_offset_seconds"), "sources": sources}
    for day in days:
        img, info = render.render(day, rules, cfg)
        img.save(os.path.join(out, f"{day['label']}.png"), optimize=True)
        aqi_vals = [v for v in (day["aqi"] or []) if v is not None]
        status[day["label"]] = {
            "date": day["date"], "hi": day["hi"], "lo": day["lo"],
            "alerts": None if day["alerts"] is None else [a["event"] for a in day["alerts"]],
            "aqi_max": max(aqi_vals) if aqi_vals else None,
            "wear": info["wear"], "fit": info["fit"]}
        print(day["label"], day["date"], f"{day['hi']}/{day['lo']}", info["wear"], info["fit"])
    with open(os.path.join(out, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    # plain key=value copy for the Kindle's busybox shell (no JSON parser there)
    with open(os.path.join(out, "status.txt"), "w", encoding="ascii", newline="\n") as f:
        f.write(f"built={status['built']}\ntoday={status['today']['date']}\n"
                f"tomorrow={status['tomorrow']['date']}\n")
    if history:
        new = not os.path.exists(history)
        with open(history, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["built", "date", "hi", "lo", "alerts", "aqi_max", "forecast", "aqi", "nws"])
            t = status["today"]
            w.writerow([status["built"], t["date"], t["hi"], t["lo"],
                        "; ".join(t["alerts"]) if t["alerts"] else ("n/a" if t["alerts"] is None else ""),
                        t["aqi_max"], sources["forecast"], sources["aqi"], sources["alerts"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="site", help="output folder")
    ap.add_argument("--sample", help="sample day name, or 'all' (no network)")
    ap.add_argument("--history", help="CSV log to append one line to (live mode)")
    args = ap.parse_args()
    cfg, rules = load("config.json"), load("clothing_rules.json")
    os.makedirs(args.out, exist_ok=True)
    if args.sample:
        names = list(samples.SAMPLES) if args.sample == "all" else [args.sample]
        build_samples(names, args.out, cfg, rules)
    else:
        build_live(args.out, cfg, rules, args.history)


if __name__ == "__main__":
    main()
