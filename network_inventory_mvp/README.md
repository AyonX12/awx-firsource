# Network Inventory AWX - Client Tracking

Read-only Juniper workstation-location inventory for AWX / Ansible Automation Controller.

The baseline maps a fixed workstation to a user (`Everest Id`) and a `Client`. AWX queries selected Juniper access switches and determines the current switch, interface and VLAN for every workstation belonging to the requested client.

## Main AWX variables

### Client-scoped scan

```yaml
target_hosts: "asw01:asw02:asw08"
client_name: "Reprise"
```

`target_hosts` may also be an AWX inventory group:

```yaml
target_hosts: "reprise_candidate_switches"
client_name: "Reprise"
```

The client comparison is case-insensitive, so `reprise`, `Reprise` and `REPRISE` match the same baseline value.

### Full inventory scan

Only use this when `target_hosts` represents the complete access-switch scope:

```yaml
target_hosts: "all_access_switches"
full_inventory_scan: true
```

Do not combine `client_name` and `full_inventory_scan`.

## Baseline

User/workstation data lives in:

```text
baseline/inventory.csv
```

Required columns include:

```text
Floor,Switch,Switch Port number,Desk Details,Client,Everest Id,Agent/Support/Empty,Port Status,WS Status,MAC Address,VLAN,IPv4 Address
```

Example:

```csv
Floor,Switch,Switch Port number,Desk Details,Client,Everest Id,Agent/Support/Empty,Port Status,WS Status,MAC Address,VLAN,IPv4 Address
34th,NY4823305571(ASW01),ge-0/0/0,P1-01,Reprise,sf752038,Agent,Active,Occupied,d0:46:0c:97:6b:dd,121,10.58.121.70
34th,FSMEXICOASW01,ge-0/0/10,P1-06,OMF,is754680,Agent,Active,Occupied,e0:70:ea:ab:f8:01,121,10.58.121.36
```

When `client_name: Reprise` is supplied, only Reprise rows are evaluated.

## Uplink exclusion

Known uplinks are stored in:

```text
vars/uplinks.yml
```

and excluded automatically by default. To temporarily include them for troubleshooting:

```yaml
exclude_uplinks: false
```

## Statuses

- `SAME`
- `PORT_MOVED`
- `SWITCH_MOVED`
- `VLAN_CHANGED`
- `SWITCH_MOVED+VLAN_CHANGED`
- `PORT_MOVED+VLAN_CHANGED`
- `NOT_FOUND_IN_SCOPE`
- `NOT_FOUND` (full scan only)
- `AMBIGUOUS`

## Safety

The collection is read-only. It runs:

```text
show ethernet-switching table
show vlans
```

No configuration commands or commits are performed.

## AWX Job Template

Point the Job Template at:

```text
network_inventory_mvp/playbooks/tower_scan.yml
```

Typical Extra Variables:

```yaml
target_hosts: "asw20:asw21"
client_name: "Reprise"
```

The Job output reports how many users/workstations for that client were tracked and lists only exceptions/movements under `Detected events`.
