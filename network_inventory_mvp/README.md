# Fixed-PC Network Inventory — AWX + Juniper

This project locates users who have a **fixed workstation** by correlating:

```text
Everest ID -> fixed workstation MAC -> live switch/port/VLAN
```

It is designed for AWX/Tower and the Juniper inventory naming already in use
(`asw01`, `asw02`, ..., `asw22`).

> Security: `baseline/inventory.csv` contains internal user/network data. Keep
> this repository private and do not commit credentials.

## What it does

1. Receives `target_hosts` from AWX Extra Variables.
2. Optionally receives one `everest_id` for a targeted search.
3. Runs read-only Junos commands on the selected switches.
4. Collects the MAC table and VLAN table.
5. Automatically excludes known uplink interfaces.
6. Looks for the workstation MAC from the baseline.
7. Returns one of these states:

- `SAME`
- `PORT_MOVED`
- `SWITCH_MOVED`
- `VLAN_CHANGED`
- `SWITCH_MOVED+VLAN_CHANGED`
- `PORT_MOVED+VLAN_CHANGED`
- `NOT_FOUND_IN_SCOPE` for a targeted search
- `NOT_FOUND` for an explicit full-inventory scan
- `AMBIGUOUS` if the MAC still has more than one non-uplink candidate

## Repository structure

```text
network_inventory_mvp/
├── baseline/
│   ├── inventory.csv
│   └── inventory.example.csv
├── collections/
│   └── requirements.yml
├── docs/
│   └── AWX_SETUP.md
├── playbooks/
│   └── tower_scan.yml
├── scripts/
│   └── compare_inventory.py
├── vars/
│   └── uplinks.yml
├── tests/
│   ├── mock_raw/
│   └── run_smoke_test.sh
├── .gitignore
├── README.md
└── requirements.txt
```

## User inventory

The real user list is:

```text
baseline/inventory.csv
```

Expected columns:

```text
Floor
Switch
Switch Port number
Desk Details
Client
Everest Id
Agent/Support/Empty
Port Status
WS Status
MAC Address
VLAN
IPv4 Address
```

MAC addresses such as:

```text
2C-58-B9-F0-05-C5
```

are normalized automatically to:

```text
2c:58:b9:f0:05:c5
```

Exact duplicate source rows are ignored and counted in the job output.

## Uplink exclusion

Uplinks are centralized in:

```text
vars/uplinks.yml
```

The current map contains ASW01-ASW22. The exclusion is on by default.

This prevents a workstation learned through another switch from generating a
false `AMBIGUOUS` result.

Example:

```text
2c:58:b9:f0:05:c5
  asw20 ge-0/2/0  -> uplink -> ignored
  asw21 ge-0/0/30 -> access -> accepted
```

## AWX targeted search

Use:

```yaml
target_hosts: "asw20:asw21"
everest_id: "ven987knc95"
```

Or use a group:

```yaml
target_hosts: "reprise_candidate_switches"
everest_id: "sf752038"
```

The playbook intentionally has **no effective default to `all`**. Omitting
`target_hosts` makes the job fail instead of scanning every switch.

## Full inventory scan

For a complete scan, omit `everest_id` and explicitly set:

```yaml
target_hosts: "all_access_switches"
full_inventory_scan: true
```

Do not use full mode with a partial switch set, because a workstation outside
that set would appear as `NOT_FOUND`.

## Commands executed on Junos

Read-only only:

```text
show ethernet-switching table
show vlans
```

No `set`, `delete`, `commit`, or configuration modules are used.

## Why `display: text`

The current AWX Execution Environment did not include `jxmlease`. This build
therefore uses `display: text`, which avoids that dependency. The Python parser
also consumes `show vlans` so it can map VLAN names to VLAN IDs when Junos does
not print a numeric VLAN directly in the MAC table.

## AWX setup

See:

```text
docs/AWX_SETUP.md
```
