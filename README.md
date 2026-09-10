# delivery-gate

**Check a data delivery against the order that was paid for.** A pipeline can write
its own `manifest.json` saying `status: ok` while the rows it shipped are the wrong
niche, half-empty, or fabricated. This is the independent check that decides whether
a delivery is clear to hand to a customer.

Stdlib only, single file, no dependencies.

```
python delivery_gate.py ORDER.json --delivery-dir DIR
```

## Why this exists

It was carved out of a real lead-generation pipeline after two failures that a
manifest alone could not catch:

- A delivery whose `manifest.json` said `status: ok` — **1 of its 8 rows matched the
  ordered niche**. The rest were orthodontists, an escape room, and a moving company,
  because the scraper's search URL carried a state segment that redirected to a
  generic city listing.
- A nightly job that **exited 0 after scraping zero records**, wrote no file, and was
  marked complete. The return code could not tell "delivered" apart from "delivered
  nothing".

Both shipped with a green light. A gate that reads the order and inspects the rows
turns both into a loud failure before a customer sees anything.

## What it checks

**Fails** on any of these:

| code | meaning |
|---|---|
| `NO_DELIVERABLE` | no CSV for this order at all (the zero-record case) |
| `DELIVERY_DIR_MISSING` / `DELIVERABLE_MISSING` / `DELIVERABLE_EMPTY` | the delivery isn't there or is empty |
| `MANIFEST_STATUS` / `MANIFEST_ERROR` / `MANIFEST_UNREADABLE` | the manifest's own verdict isn't `ok` |
| `ROWCOUNT_MISMATCH` | manifest claims a different number of rows than the CSV holds |
| `NO_MANIFEST` | a `deliveries/<order_id>/` layout with no manifest |
| `FORMAT_MISMATCH` | order asked for xlsx, only a csv exists |
| `MISSING_ORDERED_FIELD` / `NO_NAME_COLUMN` | an ordered field isn't in the delivered CSV |
| `REDACTED_PHONE` | phones delivered masked (`+121****8235`) |
| `DEMO_DATA` | fake `555-01xx` numbers, `example.com` domains or `enrich_source=sample` rows on a real order |
| `DUPLICATES` | repeated phone or email |
| `LOW_CONTACTABILITY` | under 50% of rows carry a phone, email or website |
| `NICHE_MISMATCH` / `NICHE_MOSTLY_WRONG` | fewer than half the rows match the ordered niche |
| `RECORDS_SHORT` | fewer rows than the order's `target_records` |

**Warns** (still exits 0) on: no manifest in an explicitly-named delivery dir, emails
delivered without an `email_status` provenance column, source URLs that can't be
parsed, a niche that isn't in the slug map, or sample data in a sample order.

Exit codes: `0` pass, `1` fail, `2` bad usage or unreadable order.

## Try it

Two bundled examples: one clean, one that the manifest swears is fine.

```console
$ python delivery_gate.py sample/order.json --delivery-dir sample/deliveries/demo-001
[PASS] delivery-gate — demo-001
  warn  DEMO_DATA_SAMPLE: 0 fake-555 phones, 2 example.com domains, 0 rows enrich_source=sample
  · deliverables: ['demo-001_leads.csv']
  · records_in_csv: 2
  · contactable_pct: 100.0
  · source_categories: {'roofing': 2}
```

```console
$ python delivery_gate.py sample/bad-order.json --delivery-dir sample/deliveries/demo-bad
[FAIL] delivery-gate — demo-bad
  FAIL  NICHE_MISMATCH: no delivered row matches the ordered niche — niche 'roofers' expects
        ['roofer', 'roofing', 'roofs-and-ceilings', 'roofs-ceilings']; delivered {'dental-care': 2}
  · records_in_csv: 2
  · source_categories: {'dental-care': 2}
```

In the second case the delivery's own manifest reads `"status": "ok",
"records_delivered": 2`. The gate refuses it anyway, which is the entire point: **a
producer's self-report is not evidence.**

## Options

| flag | purpose |
|---|---|
| `--delivery-dir DIR` | where the delivery lives (manifest optional when given) |
| `--deliveries DIR` | parent dir for the default `deliveries/<order_id>` layout |
| `--stem STEM` | restrict CSV discovery to one export when the dir holds several orders |
| `--niches FILE` | JSON map of `niche -> [directory category slugs]` to extend the built-in map |
| `--json FILE` | write a machine-readable report (`passed`, `failures`, `warnings`, `facts`) |

Both flat orders (`order_id`, `niche`, `location`, `target_records`, `fields`) and
nested orders (`{client, scrape{category,city,state,max_companies}, deliverable{stem}}`)
are understood.

## Design notes

Each of these is a bug that actually happened, kept as a comment at the code site:

- Never name a local `csv`. It shadows the `csv` module for the whole function and
  every later `csv.DictReader` call dies.
- Compare column names both raw (`source_url`) and normalised (`source-url`). Mixing
  the two silently skips the niche check.
- `max_companies` is a cap, not a promise. Only `target_records` is enforced.
- When a stem is given, only that stem's export counts — in a shared output directory
  an "any CSV" fallback verifies a *different* order's delivery.
- Directory location segments are inconsistent: sometimes a city slug (`new-york`),
  sometimes a state abbreviation (`ny`), sometimes absent. Unparsable rows are counted
  as unparsed, never as a mismatch — a naive parse produces confident false alarms.

## Limitations

- Niche and location are inferred from the directory URL's category segment, so a
  delivery without a `source_url`/`company_url` column can only be checked for
  structure, not relevance (`NICHE_UNCHECKABLE`).
- The slug map is data, not magic. An unmapped niche warns rather than fails; extend it
  with `--niches`.
- Only CSV rows are inspected. An `.xlsx`-only delivery is checked for existence and
  size, not contents.
- It is a gate, not a substitute for reading a sample of the rows yourself.

## Tests

```console
$ python test_delivery_gate.py
ok   clean on-niche delivery                      rc=0 (want 0)
...
11/11 cases behaved as intended
```

Eleven cases: a clean pass, and failures for wrong niche, mostly-wrong niche (1/8),
masked phones, a missing manifest, a lying manifest, a missing ordered field,
duplicate phones, demo data on a real order, plus the two regressions that matter
most — a directory slug that looks wrong but is right (`roofs-and-ceilings`), and a
manifest-less run that produced nothing.

## License

MIT — see [LICENSE](LICENSE).
