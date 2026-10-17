# CODE_STYLE.md - delivery-gate

The delivery-gate project follows a consistent Python style using only the Python standard library.

## Formatting
- Indentation: 4 spaces per level.
- Line length: Aim for under 100 characters; no strict enforcement but lines are kept readable.
- File encoding: UTF-8 (as seen in shebang and encoding declarations).

## Naming
- Functions and variables: snake_case (e.g., `order_view`, `csv_in`).
- Constants: UPPER_SNAKE_CASE (e.g., `DEMO_PHONE`, `NICHE_SLUGS`).
- Classes: CapWords (e.g., `Report`).

## Documentation
- Module and function docstrings: triple double quotes, with a brief first sentence and optional detailed description.
- Inline comments: # for explanations, design notes, and warnings (see DESIGN NOTES in delivery_gate.py).
- Type hints: used for function arguments and return values (e.g., `def norm(s: str) -> str:`).

## Imports
- Standard library imports grouped together (no third-party or local imports).
- Imported modules: argparse, csv, json, re, sys, collections, pathlib.

## Code Patterns
- Uses `pathlib.Path` for file system operations.
- Uses f-strings for string formatting (Python 3.6+).
- Regex patterns compiled at module level for reuse.
- Error handling via try-except blocks; returns integer exit codes (0=success, 1=failure, 2=usage/IO).
- CLI interface built with argparse; main function returns exit code.
- Defensive programming: checks for None, empty collections, and file existence before use.
- Data normalization: helper functions like `norm` and `getv` to handle case-insensitive and alternate column names.
- Tests: standalone script that builds temporary orders and deliveries, runs the gate as a subprocess, and asserts on exit codes and output.

## Verified against
- delivery_gate.py
- test_delivery_gate.py