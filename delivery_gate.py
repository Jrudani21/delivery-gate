#!/usr/bin/env python3
"""delivery-gate — check a data delivery against the order that was paid for.

WHY THIS EXISTS
When a pipeline writes its own `manifest.json`, that manifest is a self-report.
Nothing in it proves the buyer got what they ordered. In the pipeline this tool was
carved out of, a manifest said `status: ok` on a delivery where 1 of 8 rows matched
the ordered niche, and a nightly job reported success after scraping zero records.

So this gate reads the ORDER, reads the DELIVERY, and decides. Exit 0 = PASS,
1 = FAIL, 2 = usage/IO problem. Stdlib only — no pandas, no deps.

    python delivery_gate.py ORDER.json --delivery-dir DIR [--stem STEM] [--json REPORT]

WHAT IT CHECKS
  fails on  manifest missing/not-ok/lying about row count, missing or empty
            deliverable, format mismatch, an ordered field absent from the CSV,
            masked phones, demo markers (555-01xx / example.com / sample rows),
            duplicate phones or emails, <50% contactable rows, wrong niche or
            location derived from the source URL, short delivery vs target_records
  warns on  no manifest (manifest-less layouts), missing email provenance column,
            unparsable source URLs, unmapped niche

DESIGN NOTES (each one is a bug that actually bit — please don't reintroduce)
  * Never name a local `csv` — it shadows the csv MODULE for the whole function.
  * Compare column names both raw ("source_url") and normalised ("source-url");
    mixing them silently skips the niche check.
  * `max_companies` is a CAP, not a promise. Only `target_records` is enforced.
  * When a stem is given, only that stem's export counts. A shared output/ dir
    means an "any CSV" fallback verifies a DIFFERENT order's delivery.
  * A delivery with no manifest claims nothing, so the CSV itself is the only
    signal that anything was produced.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEMO_PHONE = re.compile(r"555-01\d\d")
DEMO_DOMAIN = re.compile(r"\b(example\.(com|org|net)|test\.com|acme\.com)\b", re.I)
REDACTED = re.compile(r"[*•·]")
NAME_COLS = {"business-name", "name", "company", "business"}
URL_COLS = {"source-url", "company-url"}

# niche -> accepted directory category slugs. Data, not code: pass --niches to
# extend without editing this file. Unmapped niche = warn, never a false FAIL.
NICHE_SLUGS = {
    "pest control": {"pest-control", "pest-control-services", "exterminator"},
    "plumbers": {"plumbing", "plumber"},
    "roofers": {"roofing", "roofer", "roofs-and-ceilings", "roofs-ceilings"},
    "electricians": {"electricians", "electrician", "electrical"},
    "cleaners": {"cleaning", "cleaning-services"},
    "landscaping": {"landscaping", "landscapers"},
    "moving": {"movers", "moving", "moving-and-storage"},
    "dentists": {"dental-care", "dentists", "dentistry"},
    "lawyers": {"lawyers", "attorneys", "legal-services"},
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").strip().lower()).strip("-")


def getv(row: dict, field: str) -> str:
    """Row value by raw or normalised column name ('source_url' / 'source-url')."""
    if field in row and row[field] is not None:
        return str(row[field])
    want = norm(field)
    for k, v in row.items():
        if k is not None and norm(k) == want and v is not None:
            return str(v)
    return ""


def order_view(order: dict) -> dict:
    """Flatten the two order shapes seen in the wild.

    flat:   {order_id, niche, location, target_records, fields, output_format}
    nested: {client: {...}, scrape: {category, city, state, max_companies},
             deliverable: {stem, out_dir}}
    """
    scrape = order.get("scrape") or {}
    deliv = order.get("deliverable") or {}
    city = order.get("city") or scrape.get("city") or ""
    state = order.get("state") or scrape.get("state") or ""
    location = order.get("location") or (f"{city}, {state}" if city and state else city)
    return {
        "oid": str(order.get("order_id") or deliv.get("stem") or ""),
        "niche": str(order.get("niche") or order.get("category") or scrape.get("category") or ""),
        "location": str(location or ""),
        "target": int(order.get("target_records") or 0),  # a promise; max_companies is not
        "stem": str(order.get("export_stem") or deliv.get("stem") or ""),
        "fields": [str(x) for x in (order.get("fields") or [])],
        "source": str(order.get("source") or scrape.get("engine") or "").lower(),
        "format": str(order.get("output_format") or "").lower(),
    }


class Report:
    def __init__(self, oid: str):
        self.oid, self.fails, self.warns, self.facts = oid, [], [], {}

    def fail(self, code: str, msg: str) -> None:
        self.fails.append(f"{code}: {msg}")

    def warn(self, code: str, msg: str) -> None:
        self.warns.append(f"{code}: {msg}")

    def render(self) -> str:
        head = f"[{'PASS' if not self.fails else 'FAIL'}] delivery-gate — {self.oid}"
        rows = [head] + [f"  FAIL  {x}" for x in self.fails] + [f"  warn  {x}" for x in self.warns]
        return "\n".join(rows + [f"  · {k}: {v}" for k, v in self.facts.items()])


def find_order(arg: str, search_dirs: str = "") -> Path | None:
    """Accept an order PATH, or an order ID/stem to search for.

    Searched dirs come from --search-dirs (comma or ':' separated) and, failing
    that, the conventional local layouts. Deliberately portable: no absolute
    machine paths, so this file stays publishable.
    """
    p = Path(arg)
    if p.is_file():
        return p
    if search_dirs:
        dirs = [Path(d.strip()) for d in search_dirs.replace(":", ",").split(",") if d.strip()]
    else:
        dirs = [Path("orders"), Path("incoming_orders"),
                Path("incoming_orders/.processed"), Path("deliveries"), Path("output")]
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            if arg in f.stem:
                return f
            try:
                o = json.loads(f.read_text(encoding="utf-8-sig"))
                ident = str(o.get("order_id") or (o.get("deliverable") or {}).get("stem") or "")
                if ident == arg:
                    return f
            except Exception:
                continue
    return None


def csv_in(deliv_dir: Path, stem: str) -> Path | None:
    """Newest CSV, restricted to `stem` when one is given (see DESIGN NOTES)."""
    cands = list(deliv_dir.glob(f"{stem}*.csv")) if stem else list(deliv_dir.glob("*.csv"))
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify a data delivery against its order.")
    ap.add_argument("order", help="order JSON path, or an order id/stem to search for")
    ap.add_argument("--search-dirs", default="",
                    help="comma-separated dirs searched when `order` is an id, not a path "
                         "(default: orders/, incoming_orders/, deliveries/, output/)")
    ap.add_argument("--delivery-dir", default=None,
                    help="delivery directory; defaults to <cwd>/deliveries/<order_id>")
    ap.add_argument("--stem", default=None, help="export stem when the dir holds many orders")
    ap.add_argument("--deliveries", default="deliveries", help="parent dir for the default layout")
    ap.add_argument("--niches", default=None, help="JSON file mapping niche -> [category slugs]")
    ap.add_argument("--json", default=None, help="write a machine-readable report here")
    args = ap.parse_args(argv)

    order_path = find_order(args.order, args.search_dirs)
    if order_path is None or not order_path.is_file():
        print(f"ERROR: cannot locate order {args.order!r} (pass a path, or --search-dirs)",
              file=sys.stderr)
        return 2
    try:
        order = json.loads(order_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"ERROR: bad order JSON: {exc}", file=sys.stderr)
        return 2

    v = order_view(order)
    oid = v["oid"] or order_path.stem
    stem = args.stem or v["stem"]
    rep = Report(oid)
    rep.facts["order_file"] = str(order_path)

    slugs = dict(NICHE_SLUGS)
    if args.niches:
        try:
            extra = json.loads(Path(args.niches).read_text(encoding="utf-8-sig"))
            slugs.update({k.lower(): set(x) for k, x in extra.items()})
        except Exception as exc:
            rep.warn("NICHES_UNREADABLE", f"{args.niches}: {exc}")

    deliv = Path(args.delivery_dir) if args.delivery_dir else Path(args.deliveries) / oid
    if not deliv.is_dir():
        rep.fail("DELIVERY_DIR_MISSING", f"no delivery directory at {deliv}")
        return finish(rep, args.json)

    # --- manifest: verified, never trusted ---
    manifest = {}
    mf = deliv / "manifest.json"
    if mf.exists():
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8-sig"))
            if str(manifest.get("status", "")).lower() != "ok":
                rep.fail("MANIFEST_STATUS",
                         f"status={manifest.get('status')!r} error={manifest.get('error')!r}")
            if str(manifest.get("error") or "").strip():
                rep.fail("MANIFEST_ERROR", str(manifest["error"])[:200])
        except Exception as exc:
            rep.fail("MANIFEST_UNREADABLE", str(exc))
    elif args.delivery_dir:
        rep.warn("NO_MANIFEST", "no manifest.json — checks derived from the CSV itself")
    else:
        rep.fail("NO_MANIFEST", f"no manifest.json in {deliv} (expected for deliveries/<order_id>)")

    # --- files ---
    files: list[Path] = []
    declared = list((manifest.get("deliverables") or {}).values())
    if declared:
        for rel in declared:
            fp = (deliv / Path(str(rel)).name)
            if not fp.exists():
                rep.fail("DELIVERABLE_MISSING", f"{rel} not found in {deliv}")
            elif fp.stat().st_size == 0:
                rep.fail("DELIVERABLE_EMPTY", f"{fp.name} is 0 bytes")
            else:
                files.append(fp)
    else:
        found = csv_in(deliv, stem)
        if found is None:
            rep.fail("NO_DELIVERABLE",
                     f"no CSV in {deliv}" + (f" matching stem {stem!r}" if stem else ""))
        elif found.stat().st_size == 0:
            rep.fail("DELIVERABLE_EMPTY", f"{found.name} is 0 bytes")
        else:
            files.append(found)
    rep.facts["deliverables"] = [f.name for f in files] or "none"

    if v["format"] and v["format"] not in {f.suffix.lower().lstrip(".") for f in files}:
        rep.fail("FORMAT_MISMATCH",
                 f"order asked {v['format']!r}, delivered {[f.suffix for f in files] or 'nothing'}")

    # --- rows ---
    rows: list[dict] = []
    header: list[str] = []
    for f in files:
        if f.suffix.lower() != ".csv":
            continue
        try:
            with f.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                header = [h for h in (reader.fieldnames or []) if h]
                rows = list(reader)
        except Exception as exc:
            rep.fail("CSV_UNPARSEABLE", f"{f.name}: {exc}")
        break

    cols = {norm(h) for h in header}
    if header:
        rep.facts["columns"] = len(header)
        for field in v["fields"]:
            accepted = {norm(field)} | (NAME_COLS if norm(field) == "business-name" else set())
            if not (accepted & cols):
                rep.fail("MISSING_ORDERED_FIELD", f"order asked {field!r}; no matching column")
        if not (NAME_COLS & cols):
            rep.fail("NO_NAME_COLUMN", "delivery has no business-name column")
        if "email" in cols and "email-status" not in cols:
            rep.warn("NO_EMAIL_PROVENANCE", "emails delivered without an email_status column")

    if rows:
        rep.facts["records_in_csv"] = len(rows)
        claimed = manifest.get("records_delivered")
        if isinstance(claimed, int) and claimed != len(rows):
            rep.fail("ROWCOUNT_MISMATCH", f"manifest claims {claimed}, CSV holds {len(rows)}")
        if v["target"] and len(rows) < v["target"]:
            msg = f"target {v['target']} records, delivered {len(rows)}"
            if v["source"] == "sample":
                rep.warn("RECORDS_SHORT_SAMPLE", msg)
            else:
                rep.fail("RECORDS_SHORT", msg)

        masked = [r for r in rows if REDACTED.search(getv(r, "phone"))]
        if masked:
            rep.fail("REDACTED_PHONE",
                     f"{len(masked)}/{len(rows)} rows have masked phone "
                     f"(e.g. {getv(masked[0], 'phone')[:20]!r}) — unusable lead data")

        fake_ph = sum(1 for r in rows if DEMO_PHONE.search(getv(r, "phone")))
        fake_web = sum(1 for r in rows if DEMO_DOMAIN.search(getv(r, "website") + getv(r, "email")))
        flagged = sum(1 for r in rows if getv(r, "enrich_source").strip().lower() == "sample")
        if fake_ph or fake_web or flagged:
            msg = (f"{fake_ph} fake-555 phones, {fake_web} example.com domains, "
                   f"{flagged} rows enrich_source=sample")
            if v["source"] == "sample":
                rep.warn("DEMO_DATA_SAMPLE", msg)
            else:
                rep.fail("DEMO_DATA", msg)

        for key in ("phone", "email"):
            dupes = [x for x, n in Counter(
                x for x in (getv(r, key).strip().lower() for r in rows) if x).items() if n > 1]
            if dupes:
                rep.fail("DUPLICATES", f"{len(dupes)} duplicate {key} values (e.g. {dupes[:3]})")

        contacts = sum(1 for r in rows
                       if any(getv(r, k).strip() for k in ("phone", "email", "website")))
        rep.facts["contactable_pct"] = round(100 * contacts / len(rows), 1)
        if rep.facts["contactable_pct"] < 50:
            rep.fail("LOW_CONTACTABILITY",
                     f"only {rep.facts['contactable_pct']}% of rows carry phone/email/website")

        # niche + location from the source URL, whose last segment is the category:
        #   /company/<id>/<slug>/<location>/<category>
        # <location> is inconsistently a city slug or a state abbreviation, and
        # id-only URLs carry no category at all — those count as unparsed, never
        # as a mismatch.
        niche = v["niche"]
        wanted = set(slugs.get(niche.lower(), ()))
        if (URL_COLS & cols) and (wanted or niche):
            cats, unparsed = Counter(), 0
            for r in rows:
                url = getv(r, "source_url") or getv(r, "company_url")
                segs = ([s for s in url.split("/company/", 1)[1].split("?")[0].split("#")[0].split("/") if s]
                        if "/company/" in url else [])
                if len(segs) < 4:
                    unparsed += 1
                    continue
                cats[segs[-1].strip().lower()] += 1
            if unparsed:
                rep.warn("SOURCE_URL_UNPARSED",
                         f"{unparsed}/{len(rows)} rows had no parsable /company/ category")
            if cats:
                rep.facts["source_categories"] = dict(cats.most_common(4))
                detail = (f"niche {niche!r} expects {sorted(wanted)}; "
                          f"delivered {dict(cats.most_common(3))}")
                if not wanted:
                    rep.warn("NICHE_UNVERIFIED",
                             f"niche {niche!r} not in the slug map — add it via --niches; "
                             f"delivered {dict(cats.most_common(3))}")
                else:
                    hit = sum(n for c, n in cats.items()
                              if any(a == c or a in c for a in wanted))
                    if hit == 0:
                        rep.fail("NICHE_MISMATCH", f"no delivered row matches the ordered niche — {detail}")
                    elif hit < len(rows) * 0.5:
                        rep.fail("NICHE_MOSTLY_WRONG",
                                 f"only {hit}/{len(rows)} rows match the ordered niche — {detail}")
                    elif hit < len(rows) * 0.8:
                        rep.warn("NICHE_PARTIAL", f"only {hit}/{len(rows)} rows match — {detail}")
        elif niche:
            rep.warn("NICHE_UNCHECKABLE", "no source_url/company_url column — niche unverifiable")

    return finish(rep, args.json, {"delivery_dir": str(deliv)})


def finish(rep: Report, json_out: str | None, extra: dict | None = None) -> int:
    print(rep.render())
    if json_out:
        payload = {"order_id": rep.oid, "passed": not rep.fails, "failures": rep.fails,
                   "warnings": rep.warns, "facts": rep.facts, **(extra or {})}
        Path(json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  · report written: {json_out}")
    return 0 if not rep.fails else 1


if __name__ == "__main__":
    sys.exit(main())
