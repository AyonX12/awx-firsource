# AWX setup

Use the existing AWX Project, Inventory and Juniper credential.

## Job Template

- Project: your Git project
- Playbook: `network_inventory_mvp/playbooks/tower_scan.yml`
- Inventory: your network inventory
- Credential: your Juniper credential

## Recommended Survey fields

### Client

Variable:

```text
client_name
```

Examples:

```text
Reprise
OMF
Robinhood
```

### Candidate switches / AWX group

Variable:

```text
target_hosts
```

Examples:

```text
asw01:asw02:asw08
```

or:

```text
reprise_candidate_switches
```

A client-scoped scan only claims that a missing workstation was not found inside the supplied switch scope. Therefore the status is `NOT_FOUND_IN_SCOPE` unless a full inventory scan is explicitly requested.

## Example

```yaml
target_hosts: "asw20:asw21"
client_name: "Reprise"
```

The comparator reads every baseline row whose `Client` equals `Reprise`, retrieves its fixed MAC address, and checks its live location across the selected switches.

## Optional seating-table update

To update the Excel seating map after movement detection, enable:

```yaml
update_seating_table: true
```

Default workbook:

```text
network_inventory_mvp/baseline/floor_33_import_template.xlsx
```

Keep the real floor seating workbook in `baseline/` with the exact name `floor_33_import_template.xlsx` before enabling the feature.

Optional overrides:

```yaml
seating_workbook_path: "/persistent/input/floor_33_import_template.xlsx"
seating_output_path: "/persistent/output/floor_33_import_template_updated.xlsx"
seating_sheet: "Seats"
```

The workbook must contain these headers:

```text
Seat ID (do not edit)
Desk Port
Agent Name
Switch Port
Switch Serial
```

The Execution Environment must include `openpyxl>=3.1.0`.
