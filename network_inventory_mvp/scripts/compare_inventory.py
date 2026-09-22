#!/usr/bin/env python3
"""Compare a fixed-PC baseline with Junos MAC tables collected by AWX.

Assumptions
-----------
* One Everest ID maps to one fixed workstation/MAC.
* The AWX playbook is read-only.
* Workstation location is the learned MAC location after known uplinks are removed.
* Client-scoped scans only make claims inside target_hosts; therefore a miss is
  NOT_FOUND_IN_SCOPE rather than a global NOT_FOUND.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

MAC_RE = re.compile(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
IF_RE = re.compile(r"(?:ge|xe|et|fe|mge)-\d+/\d+/\d+(?:\.\d+)?|ae\d+(?:\.\d+)?", re.I)
SWITCH_RE = re.compile(r"((?:ASW|DSW|CSW)\d+)", re.I)
VLAN_ID_RE = re.compile(r"^\d{1,4}$")


def norm_mac(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\\", "").strip().lower().replace("-", ":")
    match = MAC_RE.search(text)
    return match.group(0).lower() if match else text


def norm_switch(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    match = SWITCH_RE.search(text)
    return match.group(1).lower() if match else text.lower()


def norm_if(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    match = IF_RE.search(text)
    return match.group(0).split(".")[0] if match else text


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def get_command_outputs(obj: Any) -> Tuple[str, str]:
    """Return (mac_table_text, vlan_table_text) from junos_command result JSON."""
    if isinstance(obj, dict):
        stdout = obj.get("stdout")
        if isinstance(stdout, list):
            mac_text = str(stdout[0]) if len(stdout) >= 1 else ""
            vlan_text = str(stdout[1]) if len(stdout) >= 2 else ""
            return mac_text, vlan_text
        if isinstance(stdout, str):
            return stdout, ""

    # Fallback for unusual module result shapes.
    strings = list(iter_strings(obj))
    combined = "\n".join(strings)
    return combined, ""


def valid_vlan_id(value: str) -> str:
    value = value.strip()
    if VLAN_ID_RE.fullmatch(value):
        number = int(value)
        if 1 <= number <= 4094:
            return str(number)
    return ""


def parse_vlan_map(text: str) -> Dict[str, str]:
    """Build VLAN-name -> VLAN-ID map from `show vlans` text.

    Junos output differs by platform/release, so this parser intentionally uses
    a conservative relationship: the token immediately before a valid VLAN tag
    is treated as the VLAN name. Numeric names and common vlanNNN names are also
    supported directly.
    """
    mapping: Dict[str, str] = {}

    for line in text.splitlines():
        tokens = re.split(r"\s+", line.strip())
        if len(tokens) < 2:
            continue

        for idx, token in enumerate(tokens):
            vlan_id = valid_vlan_id(token)
            if not vlan_id or idx == 0:
                continue
            name = tokens[idx - 1].strip().lower()
            if not name or name in {"tag", "id", "vlan-id"}:
                continue
            mapping[name] = vlan_id
            mapping[vlan_id] = vlan_id
            break

    return mapping


def infer_vlan_from_mac_line(line: str, mac_match: re.Match[str], vlan_map: Dict[str, str]) -> str:
    before = line[: mac_match.start()].strip()
    before_tokens = re.split(r"\s+", before) if before else []

    # Most Junos variants place VLAN name/tag immediately before the MAC.
    if before_tokens:
        candidate = before_tokens[-1].strip().strip("[](),")
        direct = valid_vlan_id(candidate)
        if direct:
            return direct
        mapped = vlan_map.get(candidate.lower(), "")
        if mapped:
            return mapped
        # Common naming schemes such as vlan132 / VLAN-132 / v132.
        trailing = re.search(r"(?:vlan[-_ ]?|v)[-_ ]?(\d{1,4})$", candidate, re.I)
        if trailing:
            guessed = valid_vlan_id(trailing.group(1))
            if guessed:
                return guessed

    # Fallback: search the pre-MAC portion only, avoiding Age/NH/interface values
    # that often appear after the MAC.
    for token in reversed(before_tokens):
        direct = valid_vlan_id(token.strip("[](),"))
        if direct:
            return direct
        mapped = vlan_map.get(token.strip("[](),").lower(), "")
        if mapped:
            return mapped

    return ""


def parse_mac_table(text: str, switch: str, vlan_map: Dict[str, str]) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    for line in text.splitlines():
        mac_match = MAC_RE.search(line)
        if_match = IF_RE.search(line)
        if not (mac_match and if_match):
            continue

        mac = norm_mac(mac_match.group(0))
        interface = norm_if(if_match.group(0))
        vlan = infer_vlan_from_mac_line(line, mac_match, vlan_map)
        key = (norm_switch(switch), mac, interface, vlan)

        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "switch": switch,
                "mac": mac,
                "interface": interface,
                "vlan": vlan,
            }
        )

    return entries


def load_collected(raw_dir: Path) -> List[Dict[str, str]]:
    all_entries: List[Dict[str, str]] = []

    for path in sorted(raw_dir.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # defensive: one bad file should be visible
            print(f"WARNING: could not read {path}: {exc}")
            continue

        mac_text, vlan_text = get_command_outputs(obj)
        vlan_map = parse_vlan_map(vlan_text)
        entries = parse_mac_table(mac_text, path.stem, vlan_map)
        all_entries.extend(entries)

    return all_entries


def load_uplinks(path: Path) -> Set[Tuple[str, str]]:
    uplinks: Set[Tuple[str, str]] = set()
    if not path.exists():
        return uplinks

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(line for line in handle if not line.lstrip().startswith("#"))
        for row in reader:
            switch = norm_switch(row.get("Switch") or row.get("switch") or "")
            interface = norm_if(row.get("Interface") or row.get("interface") or "")
            if switch and interface:
                uplinks.add((switch, interface))

    return uplinks


def load_baseline(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    records: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"Switch", "Switch Port number", "Everest Id", "MAC Address"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Baseline is missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            clean = {key: (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
            clean["MAC Address"] = norm_mac(clean.get("MAC Address"))
            clean["Switch Port number"] = norm_if(clean.get("Switch Port number"))

            identity = (
                (clean.get("Everest Id") or "").lower(),
                clean.get("MAC Address") or "",
                norm_switch(clean.get("Switch") or ""),
                clean.get("Switch Port number") or "",
            )

            if identity in seen and any(identity):
                duplicates.append(clean)
                continue
            seen.add(identity)
            records.append(clean)

    return records, duplicates


def dedupe_locations(entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()
    for entry in entries:
        key = (norm_switch(entry["switch"]), entry["interface"], entry["vlan"])
        if key in seen:
            continue
        seen.add(key)
        output.append(entry)
    return output


def compare(
    baseline: List[Dict[str, str]],
    current: List[Dict[str, str]],
    uplinks: Set[Tuple[str, str]],
    scan_scope: str,
) -> Tuple[List[Dict[str, str]], int]:
    by_mac: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    excluded_uplink_entries = 0

    for entry in current:
        location_key = (norm_switch(entry["switch"]), norm_if(entry["interface"]))
        if location_key in uplinks:
            excluded_uplink_entries += 1
            continue
        if entry["mac"]:
            by_mac[entry["mac"]].append(entry)

    for mac in list(by_mac):
        by_mac[mac] = dedupe_locations(by_mac[mac])

    timestamp = datetime.now(timezone.utc).isoformat()
    output: List[Dict[str, str]] = []

    for row in baseline:
        everest = row.get("Everest Id", "")
        mac = row.get("MAC Address", "")
        if not everest or not mac:
            continue

        candidates = by_mac.get(mac, [])
        base_switch = row.get("Switch", "")
        base_interface = row.get("Switch Port number", "")
        base_vlan = row.get("VLAN", "")

        common = {
            "timestamp_utc": timestamp,
            "everest_id": everest,
            "client": row.get("Client", ""),
            "role": row.get("Agent/Support/Empty", ""),
            "mac": mac,
            "floor": row.get("Floor", ""),
            "baseline_desk": row.get("Desk Details", ""),
            "baseline_switch": base_switch,
            "baseline_interface": base_interface,
            "baseline_vlan": base_vlan,
            "baseline_ipv4": row.get("IPv4 Address", ""),
        }

        if not candidates:
            miss_status = "NOT_FOUND" if scan_scope == "full" else "NOT_FOUND_IN_SCOPE"
            output.append(
                {
                    **common,
                    "status": miss_status,
                    "current_switch": "",
                    "current_interface": "",
                    "current_vlan": "",
                }
            )
            continue

        if len(candidates) > 1:
            locations = "; ".join(
                f"{item['switch']}:{item['interface']} vlan={item['vlan'] or '?'}"
                for item in candidates
            )
            output.append(
                {
                    **common,
                    "status": "AMBIGUOUS",
                    "current_switch": locations,
                    "current_interface": "",
                    "current_vlan": "",
                }
            )
            continue

        current_location = candidates[0]
        switch_changed = norm_switch(current_location["switch"]) != norm_switch(base_switch)
        interface_changed = norm_if(current_location["interface"]) != norm_if(base_interface)
        vlan_changed = bool(
            base_vlan
            and current_location["vlan"]
            and str(current_location["vlan"]) != str(base_vlan)
        )

        if switch_changed:
            status = "SWITCH_MOVED"
        elif interface_changed:
            status = "PORT_MOVED"
        elif vlan_changed:
            status = "VLAN_CHANGED"
        else:
            status = "SAME"

        if (switch_changed or interface_changed) and vlan_changed:
            status += "+VLAN_CHANGED"

        output.append(
            {
                **common,
                "status": status,
                "current_switch": current_location["switch"],
                "current_interface": current_location["interface"],
                "current_vlan": current_location["vlan"],
            }
        )

    return output, excluded_uplink_entries


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        if fieldnames:
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fieldnames).writeheader()
        else:
            path.write_text("", encoding="utf-8")
        return

    names = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--uplinks", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--duplicates-output", required=True)
    parser.add_argument("--events-output", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--client", default="")
    parser.add_argument("--target-hosts", default="")
    parser.add_argument("--scan-scope", choices=("client", "full"), default="client")
    parser.add_argument("--print-events", action="store_true")
    args = parser.parse_args()

    try:
        baseline, duplicates = load_baseline(Path(args.baseline))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.client.strip():
        wanted_client = args.client.strip().casefold()
        baseline = [
            row
            for row in baseline
            if (row.get("Client") or "").strip().casefold() == wanted_client
        ]
        if not baseline:
            print(f"ERROR: Client not found in baseline: {args.client}")
            return 2

    current = load_collected(Path(args.raw_dir))
    uplinks = load_uplinks(Path(args.uplinks))
    results, excluded_uplink_entries = compare(baseline, current, uplinks, args.scan_scope)

    write_csv(Path(args.output), results)
    write_csv(Path(args.duplicates_output), duplicates)
    events = [row for row in results if row.get("status") != "SAME"]
    write_csv(Path(args.events_output), events, fieldnames=list(results[0].keys()) if results else None)

    counts: Dict[str, int] = defaultdict(int)
    for row in results:
        counts[row["status"]] += 1

    summary: Dict[str, Any] = {
        "scan_scope": args.scan_scope,
        "target_hosts": args.target_hosts,
        "client_filter": args.client.strip(),
        "baseline_rows": len(baseline),
        "duplicate_source_rows_ignored": len(duplicates),
        "mac_table_entries_collected": len(current),
        "uplink_entries_excluded": excluded_uplink_entries,
        "tracked_assigned_users": len(results),
        "event_count": len(events),
        "status_counts": dict(sorted(counts.items())),
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Scan scope: {args.scan_scope}")
    print(f"Target hosts: {args.target_hosts}")
    print(f"Client filter: {args.client or 'ALL CLIENTS'}")
    print(f"Baseline rows: {len(baseline)}")
    print(f"Duplicate source rows ignored: {len(duplicates)}")
    print(f"MAC-table entries collected: {len(current)}")
    print(f"Uplink MAC entries excluded: {excluded_uplink_entries}")
    print(f"Tracked assigned users: {len(results)}")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")

    if args.print_events:
        print("\nDetected events:")
        if not events:
            print("  None")
        for row in events:
            if row["status"] == "AMBIGUOUS":
                print(
                    f"  AMBIGUOUS: {row['everest_id']} | {row['mac']} | "
                    f"candidates={row['current_switch']}"
                )
            else:
                print(
                    f"  {row['status']}: {row['everest_id']} | {row['mac']} | "
                    f"{row['baseline_switch']}:{row['baseline_interface']} -> "
                    f"{row['current_switch']}:{row['current_interface']} | "
                    f"VLAN {row['baseline_vlan']} -> {row['current_vlan'] or '?'}"
                )

    print(f"Output: {args.output}")
    print(f"Events: {args.events_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
