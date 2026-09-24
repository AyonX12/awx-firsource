# Baseline files

## inventory.csv

Master relationship between client/user and fixed workstation MAC address.
The `Client` column is used when AWX receives `client_name`.

## floor_33_import_template.csv

Floor 33 seating table. Required columns:

- `Seat ID (do not edit)`
- `Desk Port`
- `Agent Name`
- `Hostname`
- `Switch Port`
- `Switch Serial`

The updater adds `Movement Comment` automatically if that column does not
already exist.

The CSV included in this package is only a small functional example. Before
running against production, replace it with the complete current Floor 33 CSV
that you already maintain in GitHub.
