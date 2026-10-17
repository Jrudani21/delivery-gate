# TESTING.md - delivery-gate

The project includes a standalone test script that validates the delivery-gate tool against various scenarios.

## Test File
- `test_delivery_gate.py`: A self-contained test that builds temporary orders and deliveries, runs the gate as a subprocess, and asserts on exit codes and output.

## Test Cases (from test_delivery_gate.py)
1. Clean on-niche delivery (expect PASS)
2. Wrong niche (expect FAIL with NICHE_MISMATCH)
3. Mostly-wrong niche (1/8 matching) (expect FAIL with NICHE_MOSTLY_WRONG)
4. Masked phones (expect FAIL with REDACTED_PHONE)
5. No manifest in deliveries layout (expect FAIL with NO_MANIFEST)
6. Manifest lies about row count (expect FAIL with ROWCOUNT_MISMATCH)
7. Ordered field missing (expect FAIL with MISSING_ORDERED_FIELD)
8. Duplicate phones (expect FAIL with DUPLICATES)
9. Demo data on a real order (expect FAIL with DEMO_DATA)
10. Real hotfrog slug roofs-and-ceilings (expect PASS)
11. Manifest-less run that produced nothing (expect FAIL with NO_DELIVERABLE)

## Running the Tests
Execute the test script with Python:
```bash
python test_delivery_gate.py
```
The script prints each test case result and exits with 0 if all pass, 1 otherwise.

## What Was Not Run
All test cases in `test_delivery_gate.py` are run by the script. No additional test frameworks or fixtures are used.

## Verified against
- test_delivery_gate.py
- delivery_gate.py
- README.md