# AWX setup

## Job Template

Use:

- **Project:** your existing `network-automation` project
- **Playbook:** `network_inventory_mvp_v3/playbooks/tower_scan.yml`
- **Inventory:** your existing Juniper inventory
- **Juniper credential:** the credential that already works with the switches

Example Extra Variables:

```yaml
target_hosts: "asw20:asw21:asw15"
client_name: "Reprise"
exclude_uplinks: true
update_seating_table: true
publish_seating_to_git: true
```

The playbook reads users from `baseline/inventory.csv` and the seating map from
`baseline/floor_33_import_template.csv`.

## GitHub write credential

The job publishes the updated seating CSV only when at least one valid movement
was applied. The publication script expects these environment variables:

- `GIT_TOKEN` - required for HTTPS GitHub repositories
- `GIT_USERNAME` - optional; defaults to `x-access-token`

If the credential already used by your AWX Project is not exposed to playbook
jobs, create a Custom Credential Type and attach the resulting credential to the
Job Template in addition to the Juniper credential.

### Custom Credential Type input configuration

```yaml
fields:
  - id: username
    type: string
    label: GitHub username
  - id: token
    type: string
    label: GitHub token
    secret: true
required:
  - token
```

### Injector configuration

```yaml
env:
  GIT_USERNAME: '{{ username }}'
  GIT_TOKEN: '{{ token }}'
```

The token is not passed as a command-line argument and is not written to the
repository.

## Git defaults

Defaults are stored in `vars/git_publish.yml`:

```yaml
git_repo_url_default: "https://github.com/awx-firsource/network_inventory_mvp.git"
git_branch_default: "main"
```

They can be overridden from AWX Extra Variables:

```yaml
git_repo_url: "https://github.com/OWNER/REPOSITORY.git"
git_branch: "main"
```

The project subdirectory is auto-detected from the directory containing this
playbook. In this package it resolves to `network_inventory_mvp_v3`.

## Update behavior

For each `PORT_MOVED` or `SWITCH_MOVED` event:

1. Locate the destination row using `Switch Serial + Switch Port`.
2. Refuse to overwrite a destination occupied by another Agent Name.
3. Clear the moved user from the old `Agent Name` cell.
4. Put the user in the destination `Agent Name` cell.
5. Write `MOVED OUT` / `MOVED IN` text in `Movement Comment`.
6. Commit and push `baseline/floor_33_import_template.csv` only when at least one row was updated.

The original `Seat ID`, `Desk Port`, `Hostname`, `Switch Port`, and
`Switch Serial` values are never changed.
