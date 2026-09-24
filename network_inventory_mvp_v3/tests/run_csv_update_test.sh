#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 "$ROOT/scripts/update_seating_csv.py" \
  --seating-csv "$ROOT/baseline/floor_33_import_template.csv" \
  --events "$ROOT/tests/events.csv" \
  --output "$TMP/floor_33_import_template_updated.csv" \
  --report "$TMP/seating_updates.csv" \
  --summary-json "$TMP/seating_summary.json" \
  --job-id 999 \
  --client Reprise
cat "$TMP/seating_summary.json"
grep '775,PP0-02,,.*MOVED OUT by AWX' "$TMP/floor_33_import_template_updated.csv" >/dev/null
grep '779,PP0-03,ven987knc95,.*MOVED IN by AWX' "$TMP/floor_33_import_template_updated.csv" >/dev/null
echo "CSV seating update test: PASS"
