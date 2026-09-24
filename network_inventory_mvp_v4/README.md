# AWX Network Inventory v4

Tracks fixed workstations by **client**, excludes switch uplinks, detects physical
moves, updates the selected floor seating CSV, and commits the updated CSV back
to GitHub.

## AWX Extra Variables

Use the same pattern you already use in AWX:

```yaml
target_hosts: "asw20:asw21:asw15"
client_name: "Reprise"
exclude_uplinks: true
floor_template: "floor_33_import_template.csv"
update_seating_table: true
publish_seating_to_git: true
```

`floor_template` remains available as the file selector. It is resolved inside
`baseline/`. For another floor, only change the value, for example:

```yaml
floor_template: "floor_34_import_template.csv"
```

This CSV version intentionally rejects `.xlsx` so AWX cannot silently update the
wrong file type.

## Files

```text
network_inventory_mvp_v4/
├── baseline/
│   ├── inventory.csv
│   ├── inventory.example.csv
│   ├── floor_33_import_template.csv
│   └── floor_33_import_template.example.csv
├── playbooks/
│   └── tower_scan.yml
├── scripts/
│   ├── compare_inventory.py
│   ├── update_seating_csv.py
│   └── publish_csv_to_git.py
├── vars/
│   ├── uplinks.yml
│   └── git_publish.yml
├── collections/
│   └── requirements.yml
└── docs/
    ├── AWX_SETUP.md
    └── EXTRA_VARS_EXAMPLE.yml
```

## Data flow

```text
baseline/inventory.csv
       ↓
filter users by client_name
       ↓
scan target_hosts
       ↓
exclude uplinks from vars/uplinks.yml
       ↓
SAME / PORT_MOVED / SWITCH_MOVED / NOT_FOUND_IN_SCOPE
       ↓
baseline/<floor_template>
       ↓
Switch Serial + Switch Port → Seat ID
       ↓
move Agent Name + write Movement Comment
       ↓
Git commit + push of the same <floor_template>
```

## Seating update behavior

For `PORT_MOVED` and `SWITCH_MOVED` events, AWX:

1. Finds the destination row by `Switch Serial + Switch Port`.
2. Clears `Agent Name` from the previous row if present.
3. Writes the Everest ID into the destination `Agent Name`.
4. Adds/updates `Movement Comment` for traceability.
5. Never overwrites a destination seat occupied by a different user.
6. Pushes the selected CSV back to GitHub only when at least one valid movement
   was applied.

Network collection remains read-only.

## Git authentication

`publish_csv_to_git.py` reads HTTPS credentials from environment variables:

```text
GIT_TOKEN
GIT_USERNAME   # optional; defaults to x-access-token
```

No token is written to the repository or passed on the git command line.
