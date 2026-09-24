# AWX setup

## Job Template

Select:

```text
Playbook: network_inventory_mvp_v4/playbooks/tower_scan.yml
```

Use Extra Variables such as:

```yaml
target_hosts: "asw20:asw21:asw15"
client_name: "Reprise"
exclude_uplinks: true
floor_template: "floor_33_import_template.csv"
update_seating_table: true
publish_seating_to_git: true
```

## Git write credential

The job that publishes the seating CSV needs environment variables:

```text
GIT_TOKEN
GIT_USERNAME
```

`GIT_USERNAME` is optional for token-based HTTPS authentication.

## Important

- `floor_template` must name a `.csv` file under `baseline/`.
- The network scan is read-only.
- GitHub is updated only when a valid movement is applied to the seating CSV.
- `target_hosts` is mandatory; the playbook never defaults to all switches.
