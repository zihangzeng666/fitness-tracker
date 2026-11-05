#!/bin/bash
# Regenerate data and push to GitHub Pages (run only after approval; repo is PUBLIC)
set -e; cd "$(dirname "$0")"
python3 build_data.py
git add -A && git commit -m "Update data $(date +%F)" && git push origin main
