#!/usr/bin/env python3
"""Regenerate data.json from the gym-log CSVs."""
import csv, json, os, sys, datetime
SRC = sys.argv[1] if len(sys.argv) > 1 else "/cursor/stores/store-4a363091-b14d-4c5e-9f44-d1e597bf058e/gym-log"
def load(n):
    with open(os.path.join(SRC, n), newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
data = {"targets": {"kcal": [2800, 3000], "protein": [140, 160]},
        "food": load("food.csv"), "daily": load("daily.csv"), "lifts": load("lifts.csv"),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
for r in data["daily"]:
    items = [f for f in data["food"] if f["date"] == r["date"]]
    r["pending_items"] = str(sum(1 for f in items if not f.get("kcal_est")))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
tmp = out + ".tmp"
json.dump(data, open(tmp, "w"), indent=1)
os.replace(tmp, out)
print("wrote", out, {k: len(v) for k, v in data.items() if isinstance(v, list)})
