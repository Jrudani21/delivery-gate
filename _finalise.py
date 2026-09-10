"""Finalise the upstream repo: document the wiring, drop the one-off scaffolding."""
from pathlib import Path
import subprocess

REPO = Path(r"E:/Local/projects/delivery-gate")

# --- 1. scaffolding must not ship (it hardcodes machine paths) ---
for name in ("_port_find_order.py", "_wire_production.py", "_e2e_wire_check.py"):
    p = REPO / name
    if p.exists():
        p.unlink()
        print("removed scaffolding:", name)

# --- 2. README: document id form + the production wiring ---
r = REPO / "README.md"
t = r.read_text(encoding="utf-8")

old_usage = "```\npython delivery_gate.py ORDER.json --delivery-dir DIR\n```"
new_usage = ("```\n# by path\npython delivery_gate.py ORDER.json --delivery-dir DIR\n\n"
             "# or by order id / stem, searching conventional layouts\n"
             "python delivery_gate.py fvr-20260831-cronlive01 --search-dirs orders,incoming_orders \\\n"
             "    --deliveries deliveries\n```")
assert old_usage in t, "usage block not found"
t = t.replace(old_usage, new_usage, 1)

old_row = "| `--deliveries DIR` | parent dir for the default `deliveries/<order_id>` layout |"
new_row = (old_row + "\n| `--search-dirs DIRS` | comma-separated dirs to search when the first argument is an "
           "order id/stem rather than a path |")
assert old_row in t
t = t.replace(old_row, new_row, 1)

prod = """## Used in production

This repo is the single source of truth for the check, not a copy of it: two scheduled
fulfilment paths (a 15-minute order watcher and a 02:00 queue job) invoke
`delivery_gate.py` directly by absolute path. Before the wiring change each path kept its
own copy of the file and they had already drifted — one accepted an order id, the other
did not. Parity is now asserted by running the same real deliveries through both callers
and comparing verdicts, and a missing gate is a loud failure (`VERIFY: skipped (gate not
found ...)`) rather than a silent pass.

## Design notes"""
t = t.replace("## Design notes", prod, 1)
r.write_text(t, encoding="utf-8")
print("README updated:", "--search-dirs DIRS" in t and "Used in production" in t)

# --- 3. commit + push ---
def sh(*cmd):
    p = subprocess.run(list(cmd), cwd=str(REPO), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()

print(sh("git", "add", "-A")[1] or "staged")
rc, out = sh("git", "-c", "user.name=Janak Rudani", "-c", "user.email=janak25rudani@gmail.com",
             "commit", "-q", "-m",
             "accept an order id (--search-dirs), and document that production consumes this repo\n\n"
             "Ported the id-lookup capability the production copy had, in portable form (no\n"
             "machine paths). Both fulfilment roots now call this file directly; their local\n"
             "copies are retired, so the two can no longer drift.")
print("commit rc:", rc, out[:120])
print(sh("git", "push", "-q", "origin", "main")[1] or "pushed")
print("ahead/behind:", sh("git", "rev-list", "--left-right", "--count", "origin/main...HEAD")[1])
print("tree clean:", sh("git", "status", "--porcelain")[1] == "")
