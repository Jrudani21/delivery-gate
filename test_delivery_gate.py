#!/usr/bin/env python3
"""Self-check for delivery_gate.py — no framework, no fixtures directory.

    python test_delivery_gate.py      # exit 0 = every case behaved

Each case builds a throwaway order + delivery in a temp dir, runs the gate as a
subprocess (so the exit code is the real contract), and asserts on the exit code
plus the failure code it reported.
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).with_name("delivery_gate.py")
BASE = Path(tempfile.mkdtemp(prefix="dg_test_"))
(BASE / "orders").mkdir()
(BASE / "deliveries").mkdir()
FIELDS = ["business_name", "phone", "address", "website", "category"]


def build(oid, order, rows, manifest=True, extra=None):
    (BASE / "orders" / f"{oid}.json").write_text(json.dumps(order), encoding="utf-8")
    d = BASE / "deliveries" / oid
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{oid}_leads.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    if manifest:
        m = {"order_id": oid, "status": "ok", "records_delivered": len(rows),
             "deliverables": {"csv": f"deliveries/{oid}/{oid}_leads.csv"}, "error": ""}
        m.update(extra or {})
        (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")


def run(order_path, *args):
    p = subprocess.run([sys.executable, str(GATE), str(order_path),
                        "--deliveries", str(BASE / "deliveries"), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def url(i, city, cat):
    return f"https://www.hotfrog.com/company/abc{i}/biz-{i}/{city}/{cat}"


ORDER = {"order_id": "", "niche": "roofers", "location": "Chicago, IL",
         "target_records": 2, "fields": FIELDS, "output_format": "csv", "source": "hotfrog"}


def rows_for(cat, n=2, **over):
    out = []
    for i in range(1, n + 1):
        r = {"business_name": f"Biz {i}", "phone": f"+131255501{i:02d}", "address": "x",
             "website": f"biz{i}.com", "category": cat, "source_url": url(i, "chicago", cat)}
        r.update(over)
        out.append(r)
    return out


results = []


def case(label, oid, order, rows, want_rc, want_code=None, manifest=True, extra=None):
    build(oid, dict(ORDER, order_id=oid, **order), rows, manifest=manifest, extra=extra)
    rc, out = run(BASE / "orders" / f"{oid}.json")
    ok = rc == want_rc and (want_code is None or want_code in out)
    print(f"{'ok  ' if ok else 'FAIL'} {label:<44} rc={rc} (want {want_rc})"
          + (f" [{want_code}]" if want_code else ""))
    if not ok:
        print("\n".join("      " + l for l in out.splitlines()[:6]))
    results.append(ok)


case("clean on-niche delivery", "t1", {}, rows_for("roofing"), 0)
case("wrong niche", "t2", {}, rows_for("dental-care"), 1, "NICHE_MISMATCH")
case("mostly-wrong niche (1/8)", "t3", {"niche": "pest control", "target_records": 8},
     rows_for("pest-control", 1) + rows_for("dental-care", 7), 1, "NICHE_MOSTLY_WRONG")
case("masked phones", "t4", {}, rows_for("roofing", phone="+121****8800"), 1, "REDACTED_PHONE")
case("no manifest in deliveries layout", "t5", {}, rows_for("roofing"), 1, "NO_MANIFEST",
     manifest=False)
case("manifest lies about row count", "t6", {}, rows_for("roofing"), 1, "ROWCOUNT_MISMATCH",
     extra={"records_delivered": 500})
case("ordered field missing", "t7", {"fields": FIELDS + ["vat_number"]}, rows_for("roofing"), 1,
     "MISSING_ORDERED_FIELD")
case("duplicate phones", "t8", {}, [dict(r, phone="+13125550000") for r in rows_for("roofing")], 1,
     "DUPLICATES")
case("demo data on a real order", "t9", {},
     rows_for("roofing", phone="+12175550199", website="example.com"), 1, "DEMO_DATA")
case("real hotfrog slug roofs-and-ceilings", "t10", {}, rows_for("roofs-and-ceilings"), 0)

# A run that produced nothing: manifest-less dir, no CSV at all.
empty = BASE / "deliveries" / "t11"
empty.mkdir(parents=True, exist_ok=True)
(BASE / "orders" / "t11.json").write_text(json.dumps(
    {"order_id": "t11", "scrape": {"category": "roofing", "city": "chicago", "state": "IL"},
     "deliverable": {"stem": "t11_leads"}}), encoding="utf-8")
rc, out = run(BASE / "orders" / "t11.json", "--delivery-dir", str(empty), "--stem", "t11_leads")
ok = rc == 1 and "NO_DELIVERABLE" in out
print(f"{'ok  ' if ok else 'FAIL'} {'manifest-less run that produced nothing':<44} "
      f"rc={rc} (want 1) [NO_DELIVERABLE]")
results.append(ok)

shutil.rmtree(BASE, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} cases behaved as intended")
sys.exit(0 if all(results) else 1)
