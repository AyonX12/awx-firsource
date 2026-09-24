#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/network_inventory_seating_test"
rm -rf "$OUT"
mkdir -p "$OUT"
python3 "$ROOT/scripts/update_seating.py" \
  --workbook "$ROOT/baseline/floor_33_import_template.xlsx" \
  --events "$ROOT/tests/seating_events.csv" \
  --output "$OUT/floor_33_import_template_updated.xlsx" \
  --report "$OUT/seating_updates.csv" \
  --summary-json "$OUT/seating_summary.json" \
  --job-id test \
  --client Reprise
printf '\nTest output: %s\n' "$OUT"
