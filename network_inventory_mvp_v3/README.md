# AWX Network Inventory v3

Tracks fixed workstations by client, excludes access-switch uplinks, detects
physical moves, updates the Floor 33 seating CSV, and commits the updated CSV
back to GitHub.

## Main AWX variables

```yaml
target_hosts: "asw20:asw21:asw15"
client_name: "Reprise"
exclude_uplinks: true
update_seating_table: true
publish_seating_to_git: true
```

`target_hosts` can be a host pattern or an AWX inventory group. The job never
falls back to scanning every switch if `target_hosts` is missing.

## Data flow

```text
baseline/inventory.csv
        |
        | Client -> Everest ID -> fixed MAC
        v
selected ASWs via target_hosts
        |
        | show ethernet-switching table + show vlans
        v
exclude uplinks
        |
        v
SAME / PORT_MOVED / SWITCH_MOVED / NOT_FOUND_IN_SCOPE
        |
        v
baseline/floor_33_import_template.csv
        |
        | Switch Serial + Switch Port -> Seat ID
        v
move Agent Name + Movement Comment
        |
        v
Git commit + push to main
```

## Safety behavior

- Network collection is read-only.
- Uplinks are excluded by default using `vars/uplinks.yml`.
- A destination seat occupied by a different user is never overwritten.
- `Seat ID`, `Desk Port`, `Hostname`, `Switch Port`, and `Switch Serial` are never modified.
- GitHub is changed only when at least one valid seat movement is applied.
- HTTPS Git credentials are read from `GIT_TOKEN` / `GIT_USERNAME` environment variables, not command arguments.

See `docs/AWX_SETUP.md` for the AWX credential and Job Template setup.
