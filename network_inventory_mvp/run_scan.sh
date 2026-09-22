#!/usr/bin/env bash
set -euo pipefail

ansible-playbook playbooks/collect_mac_table.yml "$@"
python3 scripts/compare_inventory.py
