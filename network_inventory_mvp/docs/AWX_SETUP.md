# AWX setup

## Project

Use the existing Git-backed AWX Project (for example `network-automation`) and
sync after every commit that changes this folder.

## Job Template

Recommended values:

- Project: your existing Git project
- Playbook: `network_inventory_mvp/playbooks/tower_scan.yml`
- Inventory: the inventory that already contains `asw01` ... `asw22`
- Credential: the existing Juniper credential
- Job Type: Run

The playbook does not configure the switches. It runs only:

```text
show ethernet-switching table
show vlans
```

## Extra Variables - targeted search

```yaml
target_hosts: "asw20:asw21"
everest_id: "ven987knc95"
```

`target_hosts` may also be an AWX group name:

```yaml
target_hosts: "reprise_candidate_switches"
everest_id: "sf752038"
```

## Extra Variables - full inventory

Only use this when `target_hosts` contains the complete scope you intend to
inventory:

```yaml
target_hosts: "all_access_switches"
full_inventory_scan: true
```

## Uplink exclusion

It is enabled by default. The map lives in:

```text
vars/uplinks.yml
```

Normal runs do not need an `exclude_uplinks` variable. For troubleshooting only:

```yaml
exclude_uplinks: false
```

With exclusion enabled, a MAC learned on `asw20 ge-0/2/0` is ignored because
that interface is an uplink; an occurrence on a valid access port such as
`asw21 ge-0/0/30` remains a location candidate.

## Expected output

The AWX job prints counts and detected events. It also publishes:

- `network_inventory_summary`
- `network_inventory_events_csv`

through `set_stats` as job artifacts.
