#!/usr/bin/env python3
"""Update a floor seating CSV from movement events produced by compare_inventory.py.

Only the Agent Name and Movement Comment columns are modified. A moved user is
cleared from their previous seat and written to the destination seat resolved by
Switch Serial + Switch Port. The script never overwrites a destination seat that
is occupied by a different user.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

MOVE_PREFIXES = ("SWITCH_MOVED", "PORT_MOVED")
REQUIRED_HEADERS = {
    "seat id (do not edit)",
    "desk port",
    "agent name",
    "switch port",
    "switch serial",
}
COMMENT_HEADER = "Movement Comment"


def text(value) -> str:
    return "" if value is None else str(value).strip()


def header_key(value: str) -> str:
    return re.sub(r"\s+", " ", text(value)).casefold()


def norm_switch(value: str) -> str:
    raw = text(value).casefold()
    match = re.search(r"\((asw\d+)\)", raw)
    if match:
        return match.group(1)
    match = re.search(r"(?:fsmexico)?(asw\d+)", raw)
    if match:
        return match.group(1)
    return raw.replace(" ", "")


def norm_interface(value: str) -> str:
    raw = text(value).casefold().replace(" ", "")
    raw = re.sub(r"\.(0)$", "", raw)
    # Normalize both ge0/0/18 and ge-0/0/18 to ge-0/0/18.
    match = re.match(r"^(ge|xe|et|mge)-?(\d+/\d+/\d+)$", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return raw


def is_move(status: str) -> bool:
    return any(text(status).startswith(prefix) for prefix in MOVE_PREFIXES)


def read_dict_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def validate_headers(fieldnames: List[str]) -> Dict[str, str]:
    by_key = {header_key(name): name for name in fieldnames}
    missing = sorted(REQUIRED_HEADERS.difference(by_key))
    if missing:
        raise ValueError("Missing required seating columns: " + ", ".join(missing))
    return by_key


def build_indexes(rows: List[Dict[str, str]], cols: Dict[str, str]):
    location_index: Dict[Tuple[str, str], List[int]] = {}
    agent_index: Dict[str, List[int]] = {}
    for idx, row in enumerate(rows):
        sw = norm_switch(row.get(cols["switch serial"], ""))
        iface = norm_interface(row.get(cols["switch port"], ""))
        agent = text(row.get(cols["agent name"], "")).casefold()
        if sw and iface:
            location_index.setdefault((sw, iface), []).append(idx)
        if agent:
            agent_index.setdefault(agent, []).append(idx)
    return location_index, agent_index


def seat_snapshot(row: Dict[str, str], cols: Dict[str, str]) -> Dict[str, str]:
    return {
        "seat_id": text(row.get(cols["seat id (do not edit)"], "")),
        "desk_port": text(row.get(cols["desk port"], "")),
        "agent_name": text(row.get(cols["agent name"], "")),
        "switch_port": text(row.get(cols["switch port"], "")),
        "switch_serial": text(row.get(cols["switch serial"], "")),
    }


def write_report(path: Path, rows: List[Dict[str, str]]) -> None:
    fields = [
        "everest_id",
        "movement_status",
        "update_status",
        "source_seat_id",
        "source_desk_port",
        "destination_seat_id",
        "destination_desk_port",
        "destination_switch",
        "destination_interface",
        "message",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seating-csv", required=True)
    p.add_argument("--events", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--summary-json", required=True)
    p.add_argument("--job-id", default="manual")
    p.add_argument("--client", default="")
    args = p.parse_args()

    seating_path = Path(args.seating_csv)
    events_path = Path(args.events)
    output_path = Path(args.output)
    report_path = Path(args.report)
    summary_path = Path(args.summary_json)

    if not seating_path.exists():
        print(f"ERROR: Seating CSV not found: {seating_path}", file=sys.stderr)
        return 2
    if not events_path.exists():
        print(f"ERROR: Movement events not found: {events_path}", file=sys.stderr)
        return 2

    try:
        fieldnames, rows = read_dict_rows(seating_path)
        cols = validate_headers(fieldnames)
        _, events = read_dict_rows(events_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    comment_col = next((f for f in fieldnames if header_key(f) == header_key(COMMENT_HEADER)), None)
    if not comment_col:
        comment_col = COMMENT_HEADER
        fieldnames.append(comment_col)
        for row in rows:
            row[comment_col] = ""

    move_events = [row for row in events if is_move(row.get("status", ""))]
    location_index, agent_index = build_indexes(rows, cols)
    report: List[Dict[str, str]] = []
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    updated = 0
    conflicts = 0
    destination_not_found = 0
    destination_ambiguous = 0

    for event in move_events:
        user = text(event.get("everest_id"))
        user_key = user.casefold()
        movement_status = text(event.get("status"))
        current_switch = norm_switch(event.get("current_switch", ""))
        current_interface = norm_interface(event.get("current_interface", ""))

        base_report = {
            "everest_id": user,
            "movement_status": movement_status,
            "update_status": "",
            "source_seat_id": "",
            "source_desk_port": "",
            "destination_seat_id": "",
            "destination_desk_port": "",
            "destination_switch": text(event.get("current_switch")),
            "destination_interface": text(event.get("current_interface")),
            "message": "",
        }

        destination_rows = location_index.get((current_switch, current_interface), [])
        if not destination_rows:
            destination_not_found += 1
            report.append({**base_report, "update_status": "DESTINATION_NOT_FOUND", "message": "Current switch/port is not present in floor_33_import_template.csv."})
            continue
        if len(destination_rows) > 1:
            destination_ambiguous += 1
            report.append({**base_report, "update_status": "DESTINATION_AMBIGUOUS", "message": f"Current switch/port matches {len(destination_rows)} seating rows."})
            continue

        dest_idx = destination_rows[0]
        dest_row = rows[dest_idx]
        dest = seat_snapshot(dest_row, cols)
        existing = text(dest_row.get(cols["agent name"], ""))

        source_indexes = [idx for idx in agent_index.get(user_key, []) if idx != dest_idx]
        if source_indexes:
            source = seat_snapshot(rows[source_indexes[0]], cols)
        else:
            source = {
                "seat_id": "",
                "desk_port": "",
                "agent_name": "",
                "switch_port": text(event.get("baseline_interface")),
                "switch_serial": text(event.get("baseline_switch")),
            }

        base_report.update({
            "source_seat_id": source.get("seat_id", ""),
            "source_desk_port": source.get("desk_port", ""),
            "destination_seat_id": dest.get("seat_id", ""),
            "destination_desk_port": dest.get("desk_port", ""),
        })

        if existing and existing.casefold() != user_key:
            conflicts += 1
            report.append({**base_report, "update_status": "SEAT_CONFLICT", "message": f"Destination seat is already assigned to '{existing}'. No change was made."})
            continue

        for source_idx in source_indexes:
            source_row = rows[source_idx]
            source_snap = seat_snapshot(source_row, cols)
            source_row[cols["agent name"]] = ""
            source_row[comment_col] = (
                f"MOVED OUT by AWX | User: {user} | Job: {args.job_id} | UTC: {timestamp} | "
                f"To Seat: {dest.get('seat_id') or '?'} | {dest.get('switch_serial')} {dest.get('switch_port')}"
            )

        dest_row[cols["agent name"]] = user
        dest_row[comment_col] = (
            f"MOVED IN by AWX | User: {user} | Job: {args.job_id} | UTC: {timestamp} | "
            f"Client: {args.client or text(event.get('client')) or '?'} | "
            f"From Seat: {source.get('seat_id') or '?'} | "
            f"From: {text(event.get('baseline_switch'))} {text(event.get('baseline_interface'))}"
        )

        updated += 1
        report.append({
            **base_report,
            "update_status": "UPDATED",
            "message": f"Agent Name moved to Seat {dest.get('seat_id') or '?'} and movement comments were written.",
        })
        agent_index[user_key] = [dest_idx]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    write_report(report_path, report)
    summary = {
        "source_csv": str(seating_path),
        "output_csv": str(output_path),
        "movement_events_received": len(move_events),
        "updated": updated,
        "seat_conflicts": conflicts,
        "destination_not_found": destination_not_found,
        "destination_ambiguous": destination_ambiguous,
        "report": str(report_path),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Movement events received: {len(move_events)}")
    print(f"Seats updated: {updated}")
    print(f"Seat conflicts: {conflicts}")
    print(f"Destination not found: {destination_not_found}")
    print(f"Destination ambiguous: {destination_ambiguous}")
    for item in report:
        if item["update_status"] == "UPDATED":
            print(
                f"  UPDATED: {item['everest_id']} | Seat {item['source_seat_id'] or '?'} -> "
                f"{item['destination_seat_id'] or '?'} | {item['destination_switch']}:{item['destination_interface']}"
            )
        else:
            print(f"  {item['update_status']}: {item['everest_id']} | {item['message']}")
    print(f"Updated seating CSV: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
