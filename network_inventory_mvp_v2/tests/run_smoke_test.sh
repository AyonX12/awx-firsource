#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 "$ROOT/scripts/compare_inventory.py" \
  --baseline "$ROOT/baseline/inventory.csv" \
  --raw-dir "$HERE/mock_raw" \
  --uplinks "$HERE/uplinks.csv" \
  --output "$TMP/current.csv" \
  --duplicates-output "$TMP/duplicates.csv" \
  --events-output "$TMP/events.csv" \
  --summary-json "$TMP/summary.json" \
  --target-hosts "asw20:asw21" \
  --scan-scope client \
  --client Reprise \
  --print-events

python3 - "$TMP/current.csv" "$TMP/summary.json" <<'PY'
import csv, json, sys
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8')))
assert len(rows) == 1, rows
result = rows[0]
assert result['status'] == 'SWITCH_MOVED', result
assert result['current_switch'].lower() == 'asw21', result
assert result['current_interface'] == 'ge-0/0/30', result
assert result['current_vlan'] == '132', result
summary = json.load(open(sys.argv[2], encoding='utf-8'))
assert summary['uplink_entries_excluded'] >= 1, summary
print('SMOKE TEST PASSED')
PY
