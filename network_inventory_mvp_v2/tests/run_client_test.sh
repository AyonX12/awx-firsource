#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp -d)"
python3 "$ROOT/scripts/compare_inventory.py" \
  --baseline "$ROOT/tests/client_baseline.csv" \
  --raw-dir "$ROOT/tests/client_raw" \
  --uplinks "$ROOT/tests/uplinks.csv" \
  --output "$OUT/current.csv" \
  --duplicates-output "$OUT/duplicates.csv" \
  --events-output "$OUT/events.csv" \
  --summary-json "$OUT/summary.json" \
  --target-hosts 'asw20:asw21' \
  --scan-scope client \
  --client Reprise \
  --print-events
cat "$OUT/summary.json"
