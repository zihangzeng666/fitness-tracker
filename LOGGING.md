# Logging guide (for the assistant)
Data lives in the gym-log store (`food.csv`, `lifts.csv`, `daily.csv`). Always write through `logtool.py`
(file lock, timestamped backup in `gym-log/backups/`, atomic replace, row-count guard). Then run `./deploy.sh`.

- Food:  `./logtool.py food add --date 2026-11-07 --meal dinner --item "beef bowl" --amount "1 bowl" --kcal 850 --protein 40`
  - Unknown estimate: `--kcal pending` (or omit). Shown as ⏳ pending; never counted as 0.
- Lift:  `./logtool.py lift add --date 2026-11-07 --exercise "bench press" --set 1 --weight 50 --reps 8 --feel "manageable"`
- Fix:   same command with `correct` (only changes the flags you pass); `delete` removes a row.
- Daily flags: `./logtool.py daily --date 2026-11-07 --set whey_scoops=1 --set gym_done=yes --set notes="..."`
  (total_kcal / total_protein_g are refused: they are always re-derived from food.csv.)
- Many at once: `./logtool.py batch ops.json` (or `-` for stdin), list of `{"type":"food|lift|daily","action":"add|correct|delete",...csv columns}`.
- Check: `./logtool.py summary --date 2026-11-07` (read-only).
Keys: food = date+meal+item, lift = date+exercise+set (case/space-insensitive). Re-adding an identical row is skipped;
re-adding with different values errors — use `correct`. Don't invent nutrition values; use `pending`.
Publish: `./deploy.sh` (builds data.json with generated_at, commits only if changed, no force push, waits until live).
Test with `GYMLOG_DIR=/tmp/x ./logtool.py ...` on copies, never production.
