# ARCHITECTURE.md - delivery-gate

The delivery-gate tool is a single-file, dependency-free Python script that validates data deliveries against paid orders.

## Modules and Functions

- **Argument Parsing** (`argparse`): Handles command-line inputs for order, delivery directory, stem, niches, and JSON output.
- **Order Flattening** (`order_view`): Normalizes two order shapes (flat and nested) into a common dictionary.
- **Reporting** (`Report` class): Tracks failures, warnings, and facts; renders human-readable and JSON reports.
- **File Discovery** (`find_order`, `csv_in`): Locates order JSON and delivery CSV via path or search directories.
- **Manifest Processing**: Reads and validates `manifest.json` for status and row count; treats missing manifest as warning or failure depending on layout.
- **CSV Validation**: Parses CSV, checks column presence, row counts, content validity (phones, emails, duplicates, niche match).
- **Validation Checks**: Implements all fail/warn conditions from README and code comments (e.g., `NO_DELIVERABLE`, `NICHE_MISMATCH`, `DEMO_DATA`).

## Data Flow

1. Locate order JSON (by path or ID/stem in search directories).
2. Parse and flatten order into view (`oid`, `niche`, `target`, `stem`, `fields`, `format`).
3. Determine delivery directory (explicit or default `<deliveries>/<oid>`).
4. Check for manifest.json; parse if present, validate status and error.
5. Locate deliverable CSV (from manifest `deliverables` or by stem in delivery directory).
6. Parse CSV header and rows; validate column presence for ordered fields and name column.
7. Run validation checks:
   - Manifest status/errors
   - Deliverable existence/emptiness
   - Format match
   - Row count match (manifest vs CSV, target vs CSV)
   - Phone/email validity (no masked, no demo, no duplicates)
   - Contactability (≥50% rows with phone/email/website)
   - Niche match via source URL or category column
8. Output human-readable report; optionally write JSON report.

## Design Principles

- **Stdlib Only**: No external dependencies; uses `argparse`, `csv`, `json`, `re`, `sys`, `collections`, `pathlib`.
- **Fail Fast**: Returns exit code 2 for usage/IO problems, 1 for validation failures, 0 for success.
- **Manifest Skepticism**: Manifest is treated as untrusted; CSV is the source of truth.
- **Extensible Niches**: Niche-to-slug mapping can be extended via `--niches` without code changes.
- **Defensive Parsing**: Handles missing columns, malformed JSON/CSV, and inconsistent data gracefully.

## Verified against
- README.md
- delivery_gate.py
- test_delivery_gate.py