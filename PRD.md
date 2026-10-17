# PRD.md - delivery-gate

A standalone command-line tool that independently validates data deliveries against paid orders by comparing manifest claims with actual CSV content. Prevents false positives from self-reported pipeline manifests.

Core purpose: Read order specifications, inspect delivered files, and enforce data integrity through structured checks. Exit code 0 = PASS, 1 = FAIL, 2 = usage/IO error.

Key validated criteria:
- Manifest status must be "ok" with no errors
- Deliverable files must exist and be non-empty
- Row counts must match between manifest and CSV
- Target record minimums must be met
- All ordered fields must be present in CSV columns
- No redacted/masked phone numbers (indicates unusable data)
- No demo/fake data markers (555 phones, example.com domains)
- No duplicate phone/email values
- Minimum 50% contactable rows (phone/email/website present)
- Niche relevance: >50% rows must match ordered business category
- Format consistency between order specification and delivered files

Warning conditions (non-failing):
- Missing manifest in explicitly named delivery directory
- Emails delivered without email_status provenance column
- Unparsable source URLs
- Niche not found in slug map (extensible via --niches)
- Sample data in sample orders

Supports both flat order JSON and nested order structures with scrape/deliverable objects. Uses Python stdlib only - no external dependencies.

Designed as a gatekeeper in production pipelines where two separate fulfillment paths (order watcher and nightly queue) invoke the same tool to ensure parity and prevent drift between implementations.

## Verified against
- README.md
- delivery_gate.py
- test_delivery_gate.py