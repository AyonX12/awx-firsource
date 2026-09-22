#!/usr/bin/env python3
"""Compare a baseline user/PC inventory against MAC tables collected by Ansible.

MVP assumptions:
- One Everest ID maps to one fixed workstation/MAC.
- Junos collection is read-only.
- Access-port location is inferred from MAC table entries after excluding known uplinks.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

MAC_RE = re.compile(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
IF_RE = re.compile(r"(?:ge|xe|et|fe)-\d+/\d+/\d+(?:\.\d+)?|ae\d+(?:\.\d+)?", re.I)
SWITCH_RE = re.compile(r"((?:ASW|DSW|CSW)\d+)", re.I)


def norm_mac(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\\", "").strip().lower().replace("-", ":")
    m = MAC_RE.search(s)
    return m.group(0).lower() if m else s



def norm_switch(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    m = SWITCH_RE.search(s)
    return m.group(1).lower() if m else s.lower()

def norm_if(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    m = IF_RE.search(s)
    return m.group(0).split(".")[0] if m else s


def scalar(value: Any) -> str:
    """Extract a useful scalar from Junos XML->JSON shapes."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, list):
        for item in value:
            out = scalar(item)
            if out:
                return out
        return ""
    if isinstance(value, dict):
        # Junos/Ansible XML conversions frequently wrap values in data/text keys.
        for key in ("data", "#text", "text", "value", "name"):
            if key in value:
                out = scalar(value[key])
                if out:
                    return out
        for item in value.values():
            out = scalar(item)
            if out:
                return out
    return ""


def iter_dicts(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_dicts(item)


def first_key(d: Dict[str, Any], names: Iterable[str]) -> str:
    lowered = {str(k).lower(): k for k in d.keys()}
    for name in names:
        k = lowered.get(name.lower())
        if k is not None:
            return scalar(d[k])
    return ""


def extract_entries_from_structured(obj: Any, switch: str) -> List[Dict[str, str]]:
    """Best-effort extraction from Junos XML transformed to JSON.

    The exact key nesting can vary by Junos/platform. We deliberately search
    recursively for dicts containing a MAC plus interface/VLAN-like keys.
    """
    entries: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    mac_keys = ("mac-address", "mac_address", "mac", "mac-addresses")
    vlan_keys = ("mac-vlan", "vlan", "vlan-id", "vlan_name", "mac-vlan-name")
    if_keys = (
        "mac-interface",
        "interface-name",
        "interface",
        "interface-name-list",
        "mac-interfaces-list",
        "logical-interface",
    )

    for d in iter_dicts(obj):
        mac = norm_mac(first_key(d, mac_keys))
        if not MAC_RE.fullmatch(mac):
            continue

        vlan = first_key(d, vlan_keys)
        iface = norm_if(first_key(d, if_keys))

        # If interface is nested deeper inside this entry, scan values locally.
        if not iface:
            blob = json.dumps(d, ensure_ascii=False)
            m_if = IF_RE.search(blob)
            iface = norm_if(m_if.group(0)) if m_if else ""

        if iface:
            key = (switch, mac, iface, vlan)
            if key not in seen:
                seen.add(key)
                entries.append({"switch": switch, "mac": mac, "interface": iface, "vlan": vlan})

    return entries


def extract_entries_from_xml_strings(obj: Any, switch: str) -> List[Dict[str, str]]:
    """Extract MAC/VLAN/interface tuples from XML strings returned by Junos command modules."""
    entries: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    def strings(value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v)

    for text in strings(obj):
        if "<" not in text or ">" not in text:
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            continue

        for parent in root.iter():
            leaves = []
            for elem in parent.iter():
                if elem is parent:
                    continue
                tag = elem.tag.split("}")[-1].lower()
                val = (elem.text or "").strip()
                if val:
                    leaves.append((tag, val))

            mac = ""
            iface = ""
            vlan = ""
            for tag, val in leaves:
                if not mac and "mac" in tag:
                    candidate = norm_mac(val)
                    if MAC_RE.fullmatch(candidate):
                        mac = candidate
                if not iface and ("interface" in tag or "logical-interface" in tag):
                    candidate = norm_if(val)
                    if IF_RE.fullmatch(candidate):
                        iface = candidate
                if not vlan and "vlan" in tag:
                    candidate = val.strip()
                    # Keep VLAN ID or name; ID is preferred when present.
                    m = re.search(r"\b([1-9][0-9]{0,3})\b", candidate)
                    vlan = m.group(1) if m and 1 <= int(m.group(1)) <= 4094 else candidate

            if mac and iface:
                key = (switch, mac, iface, vlan)
                if key not in seen:
                    seen.add(key)
                    entries.append({"switch": switch, "mac": mac, "interface": iface, "vlan": vlan})

    return entries


def extract_entries_from_text(obj: Any, switch: str) -> List[Dict[str, str]]:
    """Fallback parser if a device/module returns text instead of structured XML."""
    text = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    entries: List[Dict[str, str]] = []
    seen = set()
    for line in text.split("\\n"):
        m_mac = MAC_RE.search(line)
        m_if = IF_RE.search(line)
        if not (m_mac and m_if):
            continue
        mac = norm_mac(m_mac.group(0))
        iface = norm_if(m_if.group(0))
        # VLAN extraction is intentionally conservative in fallback mode.
        vlan = ""
        tokens = re.split(r"\s+", line.strip())
        for token in tokens:
            if token.isdigit() and 1 <= int(token) <= 4094:
                vlan = token
                break
        key = (switch, mac, iface, vlan)
        if key not in seen:
            seen.add(key)
            entries.append({"switch": switch, "mac": mac, "interface": iface, "vlan": vlan})
    return entries


def load_collected(raw_dir: Path) -> List[Dict[str, str]]:
    all_entries: List[Dict[str, str]] = []
    for path in sorted(raw_dir.glob("*.json")):
        switch = path.stem
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"WARNING: could not read {path}: {exc}")
            continue
        entries = extract_entries_from_structured(obj, switch)
        if not entries:
            entries = extract_entries_from_xml_strings(obj, switch)
        if not entries:
            entries = extract_entries_from_text(obj, switch)
        all_entries.extend(entries)
    return all_entries


def load_uplinks(path: Path) -> Set[Tuple[str, str]]:
    out: Set[Tuple[str, str]] = set()
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(line for line in f if not line.lstrip().startswith("#")):
            sw = norm_switch(row.get("Switch") or "")
            iface = norm_if(row.get("Interface") or "")
            if sw and iface:
                out.add((sw, iface))
    return out


def load_baseline(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    records: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = []
    seen = set()

    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            clean = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            clean["MAC Address"] = norm_mac(clean.get("MAC Address"))
            clean["Switch Port number"] = norm_if(clean.get("Switch Port number"))
            ident = (
                clean.get("Everest Id", ""),
                clean.get("MAC Address", ""),
                clean.get("Switch", ""),
                clean.get("Switch Port number", ""),
            )
            if ident in seen and any(ident):
                duplicates.append(clean)
                continue
            seen.add(ident)
            records.append(clean)

    return records, duplicates


def compare(
    baseline: List[Dict[str, str]],
    current: List[Dict[str, str]],
    uplinks: Set[Tuple[str, str]],
) -> List[Dict[str, str]]:
    by_mac: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for entry in current:
        if (norm_switch(entry["switch"]), entry["interface"]) in uplinks:
            continue
        if entry["mac"]:
            by_mac[entry["mac"]].append(entry)

    now = datetime.now(timezone.utc).isoformat()
    output: List[Dict[str, str]] = []

    for row in baseline:
        everest = row.get("Everest Id", "")
        mac = row.get("MAC Address", "")

        # Only track assigned fixed-PC users in the MVP.
        if not everest or not mac:
            continue

        candidates = by_mac.get(mac, [])
        base_sw = row.get("Switch", "")
        base_if = row.get("Switch Port number", "")
        base_vlan = row.get("VLAN", "")

        common = {
            "timestamp_utc": now,
            "everest_id": everest,
            "client": row.get("Client", ""),
            "role": row.get("Agent/Support/Empty", ""),
            "mac": mac,
            "floor": row.get("Floor", ""),
            "baseline_desk": row.get("Desk Details", ""),
            "baseline_switch": base_sw,
            "baseline_interface": base_if,
            "baseline_vlan": base_vlan,
            "baseline_ipv4": row.get("IPv4 Address", ""),
        }

        if not candidates:
            output.append({**common, "status": "NOT_FOUND", "current_switch": "", "current_interface": "", "current_vlan": ""})
            continue

        if len(candidates) > 1:
            locs = "; ".join(f"{x['switch']}:{x['interface']} vlan={x['vlan']}" for x in candidates)
            output.append({**common, "status": "AMBIGUOUS", "current_switch": locs, "current_interface": "", "current_vlan": ""})
            continue

        cur = candidates[0]
        sw_changed = norm_switch(cur["switch"]) != norm_switch(base_sw)
        if_changed = cur["interface"] != base_if
        vlan_changed = bool(base_vlan and cur["vlan"] and cur["vlan"] != base_vlan)

        if sw_changed:
            status = "SWITCH_MOVED"
        elif if_changed:
            status = "PORT_MOVED"
        elif vlan_changed:
            status = "VLAN_CHANGED"
        else:
            status = "SAME"

        if (sw_changed or if_changed) and vlan_changed:
            status += "+VLAN_CHANGED"

        output.append({
            **common,
            "status": status,
            "current_switch": cur["switch"],
            "current_interface": cur["interface"],
            "current_vlan": cur["vlan"],
        })

    return output


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", default="baseline/inventory.csv")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--uplinks", default="baseline/uplinks.csv")
    p.add_argument("--output", default="data/output/current_inventory.csv")
    p.add_argument("--duplicates-output", default="data/output/source_duplicates.csv")
    p.add_argument("--events-output", default="data/output/events.csv")
    p.add_argument("--summary-json", default="")
    p.add_argument("--print-events", action="store_true")
    p.add_argument("--everest-id", default="", help="Optional Everest ID for a targeted scan")
    args = p.parse_args()

    baseline, duplicates = load_baseline(Path(args.baseline))
    if args.everest_id.strip():
        wanted = args.everest_id.strip().lower()
        baseline = [row for row in baseline if (row.get("Everest Id") or "").strip().lower() == wanted]
        if not baseline:
            print(f"ERROR: Everest ID not found in baseline: {args.everest_id}")
            return 2
    current = load_collected(Path(args.raw_dir))
    uplinks = load_uplinks(Path(args.uplinks))
    result = compare(baseline, current, uplinks)

    write_csv(Path(args.output), result)
    write_csv(Path(args.duplicates_output), duplicates)
    events = [row for row in result if row.get("status") != "SAME"]
    write_csv(Path(args.events_output), events)

    counts: Dict[str, int] = defaultdict(int)
    for row in result:
        counts[row["status"]] += 1

    print(f"Baseline rows: {len(baseline)}")
    print(f"Duplicate source rows ignored: {len(duplicates)}")
    print(f"MAC-table entries collected: {len(current)}")
    print(f"Tracked assigned users: {len(result)}")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")
    summary = {
        "baseline_rows": len(baseline),
        "duplicate_source_rows_ignored": len(duplicates),
        "mac_table_entries_collected": len(current),
        "tracked_assigned_users": len(result),
        "event_count": len(events),
        "status_counts": dict(sorted(counts.items())),
        "everest_id_filter": args.everest_id.strip(),
    }

    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if args.print_events:
        print("\nDetected events:")
        if not events:
            print("  None")
        for row in events:
            print(
                f"  {row['status']}: {row['everest_id']} | {row['mac']} | "
                f"{row['baseline_switch']}:{row['baseline_interface']} -> "
                f"{row['current_switch']}:{row['current_interface']} | "
                f"VLAN {row['baseline_vlan']} -> {row['current_vlan']}"
            )

    print(f"Output: {args.output}")
    print(f"Events: {args.events_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
