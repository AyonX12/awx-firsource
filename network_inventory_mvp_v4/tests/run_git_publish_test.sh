#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
BARE="$TMP/remote.git"
SEED="$TMP/seed"
UPDATED="$TMP/updated.csv"
git init --bare "$BARE" >/dev/null
git clone "$BARE" "$SEED" >/dev/null 2>&1
mkdir -p "$SEED/network_inventory_mvp_v4/baseline"
printf 'Seat ID (do not edit),Agent Name\n1,old\n' > "$SEED/network_inventory_mvp_v4/baseline/floor_33_import_template.csv"
git -C "$SEED" config user.name test
git -C "$SEED" config user.email test@example.com
git -C "$SEED" add .
git -C "$SEED" commit -m seed >/dev/null
git -C "$SEED" branch -M main
git -C "$SEED" push origin main >/dev/null 2>&1
printf 'Seat ID (do not edit),Agent Name\n1,new\n' > "$UPDATED"
python3 "$ROOT/scripts/publish_csv_to_git.py" \
  --repo-url "$BARE" \
  --branch main \
  --project-subdir network_inventory_mvp_v4 \
  --source-file "$UPDATED" \
  --workspace "$TMP/publish" \
  --commit-message 'test update' \
  --git-user-name test \
  --git-user-email test@example.com
VERIFY="$TMP/verify"
git clone --branch main "$BARE" "$VERIFY" >/dev/null 2>&1
grep '1,new' "$VERIFY/network_inventory_mvp_v4/baseline/floor_33_import_template.csv" >/dev/null
echo "Git publication test: PASS"
