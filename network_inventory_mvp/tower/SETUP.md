# Ansible Tower setup — Network Inventory MVP

This variant is designed to run as a **Tower / Automation Controller Job Template**.

## Architecture

Tower owns:

- the inventory of Juniper switches;
- the credential used to connect to the switches;
- the Project containing this repository;
- the Job Template;
- the schedule.

The project owns:

- the fixed-PC baseline (`baseline/inventory.csv`);
- the uplink exclusion list (`baseline/uplinks.csv`);
- the read-only collector;
- the comparison logic.

The first Tower version does **not** rely on persistent local files between jobs. Each run writes temporary files only for the lifetime of that job, then publishes the summary and event CSV as Tower job artifacts.

## 1. Project

Put this folder in the Git repository used by Tower, then create/sync a Tower Project pointing to that repository.

The playbook used by the Job Template is:

```text
playbooks/tower_scan.yml
```

## 2. Tower Inventory

Create a group named exactly:

```text
mexico_access_switches
```

Add the access switches as hosts. Example:

```text
FSMEXICOASW01 -> 10.x.x.1
FSMEXICOASW02 -> 10.x.x.2
FSMEXICOASW08 -> 10.x.x.8
```

For each host, set the management address with `ansible_host` if the Tower hostname is not itself resolvable.

Example host variables:

```yaml
ansible_host: 10.x.x.8
```

The playbook already supplies:

```yaml
ansible_connection: ansible.netcommon.netconf
ansible_network_os: juniper.device.junos
ansible_port: 830
```

## 3. Credential

Attach the Tower credential that injects the Junos username/password (commonly a Machine credential, depending on the Tower/AAP version and local credential design).

Use a read-only network account for this MVP.

Do not put the production password in the Git repository.

## 4. Dependencies / Execution Environment

The execution environment needs the `juniper.device` collection plus NETCONF support.

Collection file:

```text
collections/requirements.yml
```

Python dependency file:

```text
requirements.txt
```

If your Tower is an older release that uses custom Python virtual environments rather than Execution Environments, install these dependencies in the virtual environment assigned to the Job Template instead.

## 5. Job Template

Recommended initial settings:

```text
Name: Network Inventory - Juniper Scan
Job Type: Run
Inventory: <your network inventory>
Project: <this project>
Playbook: playbooks/tower_scan.yml
Credential: <read-only Junos credential>
Forks: 5-10 for the first test
Verbosity: 1 or 2
```

Run it first with only 1-2 switches in `mexico_access_switches` or use Tower's Limit field.

## 6. Baseline

Replace:

```text
baseline/inventory.csv
```

with the production inventory using these headers:

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

The tracking rule is:

```text
Everest Id <-> fixed workstation MAC
```

## 7. Exclude uplinks

Maintain:

```text
baseline/uplinks.csv
```

Example:

```csv
Switch,Interface
FSMEXICOASW01,ge-0/0/47
FSMEXICOASW01,ge-0/0/48
FSMEXICOASW08,ae0
```

This prevents a MAC learned through an uplink/trunk from being treated as the user's physical endpoint location.

## 8. Tower job result

The Job Output will show counters such as:

```text
SAME: 135
SWITCH_MOVED: 4
PORT_MOVED: 8
NOT_FOUND: 19
```

It will also print each non-SAME event.

Two job artifacts are published with `set_stats`:

```text
network_inventory_summary
network_inventory_events_csv
```

These are useful for a later Workflow node, notification step, or API integration.

## 9. Scheduling

After validating the parser and load against the Juniper switches, create a Tower Schedule for the Job Template.

Start conservatively (for example every 5 minutes). After validating execution time, switch CPU impact, Tower capacity and false positives, the polling interval can be reduced if needed.

## Important persistence note

Tower job artifacts are suitable for showing/passing the result of a run, but they are not the long-term history database for this solution.

For the next phase, use an external persistent store such as PostgreSQL for:

- current device location;
- first/last seen;
- previous location;
- movement history;
- historical VLAN changes.

That keeps Tower as the automation/orchestration layer instead of making its execution filesystem the database.
