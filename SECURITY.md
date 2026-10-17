# SECURITY.md - delivery-gate

The tool operates within the trust boundary of the executing user's filesystem access. It reads order JSON files and delivery CSV/manifest files from paths provided by the user, and optionally writes a JSON report file. No network calls are made.

Controls:
- Input files are parsed using stdlib `json` and `csv` modules only; no evaluation or execution of input content.
- No external dependencies, eliminating supply-chain risks from third-party packages.
- No handling of secrets, API keys, or tokens; the tool does not process or transmit sensitive data beyond reading user-specified files.
- File operations are restricted to paths explicitly provided via command-line arguments or derived from them (order ID/stem, delivery directory).

As a public repository, no additional project-specific security measures are in place beyond the stdlib-only design and minimal attack surface.

## Verified against
- README.md
- delivery_gate.py
- test_delivery_gate.py