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
