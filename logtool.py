#!/usr/bin/env python3
"""Safe logger for Jason's gym-log CSVs. See LOGGING.md.
Every write: file lock -> backup -> atomic replace -> daily totals re-derived from food.csv.
"""
import argparse, csv, fcntl, json, os, shutil, sys, tempfile, time, contextlib
SRC = os.environ.get("GYMLOG_DIR", "/cursor/stores/store-4a363091-b14d-4c5e-9f44-d1e597bf058e/gym-log")
COLS = {
 "food.csv": ["date","meal","item","amount","kcal_est","protein_g_est"],
 "lifts.csv": ["date","exercise","set","weight_kg","reps","feel"],
 "daily.csv": ["date","total_kcal","total_protein_g","whey_scoops","peanut_butter_tbsp","gym_day","gym_done","tennis","soreness_notes","soreness_0_10","notes"],
}
KEYS = {"food.csv": ["date","meal","item"], "lifts.csv": ["date","exercise","set"], "daily.csv": ["date"]}
norm = lambda s: " ".join(str(s or "").strip().lower().split())
def key(name, r): return "|".join(norm(r.get(k)) for k in KEYS[name])

@contextlib.contextmanager
def locked():
    with open(os.path.join(SRC, ".lock"), "a+") as lf:
        for _ in range(100):
            try: fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except OSError: time.sleep(0.1)
        else: sys.exit("ERROR: gym-log is locked by another writer")
        try: yield
        finally: fcntl.flock(lf, fcntl.LOCK_UN)

def load(name):
    p = os.path.join(SRC, name)
    if not os.path.exists(p): return []
    with open(p, newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]

def save(name, rows, before):
    p = os.path.join(SRC, name)
    if os.path.exists(p):
        bd = os.path.join(SRC, "backups"); os.makedirs(bd, exist_ok=True)
        shutil.copyfile(p, os.path.join(bd, f"{name}.{time.strftime('%Y%m%dT%H%M%S')}.{os.getpid()}.bak"))
    cols = COLS[name] + [c for r in rows for c in r if c not in COLS[name]]
    cols = list(dict.fromkeys(cols))
    fd, tmp = tempfile.mkstemp(dir=SRC, prefix=f".{name}.")
    with os.fdopen(fd, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n"); w.writeheader()
        for r in rows: w.writerow({c: r.get(c, "") for c in cols})
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    # guard: never silently lose rows
    after = len(load(name))
    if after < before: sys.exit(f"ERROR: {name} row count dropped {before}->{after}; restore from backups/")

def num(v):
    try: return float(str(v).strip())
    except (TypeError, ValueError): return None

def derive(food, daily, date):
    """Daily totals = sum of KNOWN food estimates; pending items are counted, never treated as 0."""
    items = [r for r in food if r["date"] == date]
    if not items: return None
    k = [num(r.get("kcal_est")) for r in items]; p = [num(r.get("protein_g_est")) for r in items]
    row = next((r for r in daily if r["date"] == date), None)
    if row is None:
        row = {c: "" for c in COLS["daily.csv"]}; row["date"] = date; daily.append(row)
    row["total_kcal"] = str(round(sum(x for x in k if x is not None)))
    row["total_protein_g"] = str(round(sum(x for x in p if x is not None)))
    return {"kcal": row["total_kcal"], "protein": row["total_protein_g"],
            "pending_kcal_items": sum(x is None for x in k), "pending_protein_items": sum(x is None for x in p)}

def upsert(name, rec, mode):
    """mode: add (skip exact dup, refuse conflicting dup) | correct (must exist) | delete."""
    rows = load(name); before = len(rows); k = key(name, rec)
    hit = [i for i, r in enumerate(rows) if key(name, r) == k]
    if len(hit) > 1: sys.exit(f"ERROR: {len(hit)} existing rows share key {k!r}; fix manually")
    if mode == "add":
        if hit:
            old = rows[hit[0]]
            if all(norm(old.get(c)) == norm(v) for c, v in rec.items() if v is not None):
                return f"SKIP duplicate {k}", rows, None
            sys.exit(f"ERROR: {k!r} already exists with different values: {old}\n  use 'correct' to change it")
        rows.append({c: (rec.get(c) or "") for c in COLS[name]}); msg = f"ADDED {k}"
    elif mode == "correct":
        if not hit: sys.exit(f"ERROR: no row with key {k!r} to correct")
        old = dict(rows[hit[0]])
        for c, v in rec.items():
            if v is not None: rows[hit[0]][c] = v
        msg = f"CORRECTED {k}: {old} -> {rows[hit[0]]}"
    elif mode == "delete":
        if not hit: sys.exit(f"ERROR: no row with key {k!r} to delete")
        rows.pop(hit[0]); before -= 1; msg = f"DELETED {k}"
    return msg, rows, before

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("food"); f.add_argument("action", choices=["add","correct","delete"])
    for a in ["date","meal","item"]: f.add_argument("--"+a, required=True)
    f.add_argument("--amount"); f.add_argument("--kcal", help="omit or 'pending' if unknown"); f.add_argument("--protein")
    l = sp.add_parser("lift"); l.add_argument("action", choices=["add","correct","delete"])
    for a in ["date","exercise","set"]: l.add_argument("--"+a, required=True)
    l.add_argument("--weight"); l.add_argument("--reps"); l.add_argument("--feel")
    d = sp.add_parser("daily"); d.add_argument("--date", required=True)
    d.add_argument("--set", action="append", default=[], metavar="col=value", help="non-total columns only")
    b = sp.add_parser("batch", help="JSON list of {type:food|lift|daily, action, ...fields}"); b.add_argument("file")
    s = sp.add_parser("summary"); s.add_argument("--date", required=True)
    a = ap.parse_args()
    pend = lambda v: None if v is None else ("" if norm(v) in ("pending", "unknown", "?") else v)
    ops = []
    if a.cmd == "batch":
        ops = json.load(open(a.file) if a.file != "-" else sys.stdin)
    elif a.cmd == "food":
        ops = [dict(type="food", action=a.action, date=a.date, meal=a.meal, item=a.item, amount=a.amount, kcal_est=pend(a.kcal), protein_g_est=pend(a.protein))]
    elif a.cmd == "lift":
        ops = [dict(type="lift", action=a.action, date=a.date, exercise=a.exercise, set=a.set, weight_kg=a.weight, reps=a.reps, feel=a.feel)]
    elif a.cmd == "summary":
        ops = [dict(type="summary", date=a.date)]
    elif a.cmd == "daily":
        ops = [dict(type="daily", date=a.date, **dict(x.split("=", 1) for x in a.set))]
    with locked():
        touched = set()
        for op in ops:
            op = dict(op); t = op.pop("type"); act = op.pop("action", "add"); touched.add(op["date"])
            if t == "food" and act == "add":
                op.setdefault("kcal_est", ""); op.setdefault("protein_g_est", "")
            if t == "summary": continue
            if t == "daily":
                bad = {"total_kcal", "total_protein_g"} & set(op)
                if bad: sys.exit("ERROR: totals are derived from food.csv; do not set them")
                daily = load("daily.csv"); n = len(daily)
                row = next((r for r in daily if r["date"] == op["date"]), None)
                if row is None: row = {c: "" for c in COLS["daily.csv"]}; daily.append(row)
                row.update({k: str(v) for k, v in op.items()}); save("daily.csv", daily, n)
                print("DAILY", op); continue
            name = "food.csv" if t == "food" else "lifts.csv"
            msg, rows, before = upsert(name, {k: (None if v is None else str(v)) for k, v in op.items()}, act)
            if before is not None: save(name, rows, before)
            print(msg)
        food, daily = load("food.csv"), load("daily.csv"); n = len(daily)
        for dt in sorted(touched):
            r = derive(food, daily, dt)
            if r: print(f"TOTAL {dt}: {r['kcal']} kcal, {r['protein']} g protein"
                        + (f" (+{r['pending_kcal_items']} item(s) kcal pending)" if r['pending_kcal_items'] else ""))
        if touched and a.cmd != "summary": save("daily.csv", daily, n)

if __name__ == "__main__": main()
