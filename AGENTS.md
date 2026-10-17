# AGENTS.md - delivery-gate

Single-file command-line tool that checks a data delivery against its order. Standard
library only. See `README.md` for usage and `PRD.md` for the purpose.

## Run

- Help: `python delivery_gate.py --help`
- Check a delivery: `python delivery_gate.py <order.json or order id> [--delivery-dir DIR] [--stem STEM]`
- Exit codes: 0 = PASS, 1 = FAIL, 2 = usage or I/O error.

## Test

- `python test_delivery_gate.py` (no framework; exit 0 means every case behaved). See `TESTING.md`.

## Conventions

- Keep it standard library only and in one file unless the owner asks otherwise.
- Do not add network calls; the gate reads local files only.
- Plain hyphens in text, no em-dashes. Follow `CODE_STYLE.md`.
- Never put real customer data in `sample/` or in tests.

## Verified against

`README.md`, `delivery_gate.py` (argparse block), `test_delivery_gate.py` (header docstring).
