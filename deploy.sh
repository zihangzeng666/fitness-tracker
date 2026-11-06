#!/bin/bash
# Regenerate data.json and push to GitHub Pages (repo is PUBLIC; publishing already approved).
# Safe: no force push, no reset. Commits only when something changed; verifies live data afterwards.
set -euo pipefail; cd "$(dirname "$0")"
python3 build_data.py
git add -A
if git diff --cached --quiet; then echo "nothing to commit"; else git commit -q -m "Update data $(date +%F\ %H:%M)"; fi
git pull --rebase --ff-only -q origin main 2>/dev/null || git pull --rebase -q origin main
git push -q origin main
want=$(python3 -c 'import json;print(json.load(open("data.json"))["generated_at"])')
for i in $(seq 1 30); do
  got=$(curl -fsS "https://zihangzeng666.github.io/fitness-tracker/data.json?nc=$RANDOM$i" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("generated_at",""))' || true)
  [ "$got" = "$want" ] && { echo "LIVE OK generated_at=$got"; exit 0; }
  sleep 10
done
echo "WARNING: pushed, but live data.json not updated yet (Pages may be slow)"; exit 1
