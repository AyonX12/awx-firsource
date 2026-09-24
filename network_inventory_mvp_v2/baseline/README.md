# Baseline files

This folder contains the two source files used by the AWX workflow.

## `inventory.csv`
Maps each fixed PC to its user, client, baseline switch/port, VLAN and IP.

## `floor_33_import_template.xlsx`
Physical seat map used by the optional seating update step. Keep the real workbook in this folder with this exact filename.

Required headers in the seating workbook:

- `Seat ID (do not edit)`
- `Desk Port`
- `Agent Name`
- `Switch Port`
- `Switch Serial`

`Hostname` may also be present and is preserved.

When a user is detected as moved, only the `Agent Name` cells are modified: the old occurrence is cleared, the destination seat receives the Everest ID, and a comment is added to the destination `Agent Name` cell describing the movement and AWX Job ID.

The original workbook in Git is never overwritten during a job. The default generated output is:

`/tmp/network_inventory_<JOB_ID>/output/floor_33_import_template_updated.xlsx`

Use `seating_output_path` if you have a persistent mounted path.
