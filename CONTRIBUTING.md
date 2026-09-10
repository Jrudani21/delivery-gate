# Contributing

Single-maintainer project, so there's no process to follow — but issues and patches
are welcome.

- Run `python test_delivery_gate.py` before opening a PR; it exits non-zero if any
  case misbehaves, and a new failure code should come with a case of its own.
- Keep it stdlib-only. If a change needs a dependency, it probably belongs in a fork.
- A new niche slug belongs in `NICHE_SLUGS` (or your own `--niches` file), not in the
  checking logic.
