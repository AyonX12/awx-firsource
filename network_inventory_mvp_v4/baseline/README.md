# Baseline files

- `inventory.csv`: master mapping of Client / Everest ID / fixed MAC / original network location.
- `floor_33_import_template.csv`: live seating table for Floor 33.
- `floor_33_import_template.example.csv`: example copy.

The AWX variable `floor_template` chooses which CSV under this directory is
updated and pushed back to GitHub.

Example:

```yaml
floor_template: "floor_33_import_template.csv"
```

For another floor, add the CSV here and change only the AWX variable.
