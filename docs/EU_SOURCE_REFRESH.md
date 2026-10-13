# EU source updates and legal application dates

## Two different questions

1. **What has the EU published?** The DG SANTE API can provide a current
   source snapshot of residue records and active substances.
2. **Which residue definition applies to a product on a particular date?**
   This is a legal interpretation question. A record's version number, a
   publication date, and a retrieval timestamp cannot answer it by themselves.

The [Commission's pesticide MRL Q&A](https://food.ec.europa.eu/plants/pesticides/maximum-residue-levels/qas-pesticides_en)
distinguishes publication, entry into force, application date and transitional
provisions. A later-published definition may not yet apply. MRL provisions,
commodity exceptions and dates must be verified against their legal sources.

**Do not use the latest record ID/version as evidence of legal applicability.**
Until that work is implemented, the `rd_bridge.resolve` lookup reports
`applicability.status = "unverified"`. Its `status = "resolved"` only
indicates that the *mapped source definition* has a PARAM link.

## How the new source workflow works

[Update EU source snapshots](../.github/workflows/eu_sources.yml) runs weekly
(Mondays 06:00 UTC) and on demand. It uses two endpoints, pinned to
`api-version=v3.0`:

- `pesticide-residues` with `pesticide_residue_lg=EN`.
- `active-substances`.

It paginates to completion, retains **every response field and original row**
(including duplicate records), and stages:

- `data/eu_sources/residues_full.json`
- `data/eu_sources/active_substances_full.json`
- `data/eu_sources/manifest.json` (source URLs, field names, counts, pages,
  candidate date fields and SHA-256 checksums)

It also uploads a Markdown review report as a workflow artifact. If source data
have changed, it opens a **draft PR**. The first run produces the initial
unapproved full-field snapshots; subsequent runs show diffs.

A broken API, missing required fields, incomplete pagination, empty results or
an implausibly large drop in row counts **fails without updating snapshots**.
Date-like field names and example values are reported for investigation; they
are **not automatically treated as legal application dates**. Schema additions
are preserved, never filtered out.

This workflow intentionally **does not update** `data/residues_en.json`,
`data/active_substances.json`, `data/residue_param_map.json` or model caches.
It therefore cannot activate a newly published but not-yet-applicable
definition by accident.

Run the same checks locally (Python 3.10+; standard library only):

```bash
python -m unittest discover -s tests -t .
python -m rd_bridge.eu_refresh --report eu-refresh-report.md
```

## What is and is not meant by “all EU data”

The new snapshots preserve **all raw fields** from the two endpoints that the
project currently uses. They are not a copy of the entire EU Pesticides
Database. There are separate EU API endpoints for MRL values, product
associations and downloadable MRL datasets. These may be required for legal
dates and historical interpretations; they have **not** yet been integrated
or independently schema-validated here.

The previously committed residue snapshot contains only eight fields and no
date field; the five-field `data/active_substances.json` is a deliberate
projection, **not** a complete active-substance source. The full-field
snapshot prevents further loss of attributes once a successful new fetch is
possible.

## Requirements before promoting staged data

1. Determine and document the authoritative *application date* source and
   whether it refers to an entire RD, an MRL/product combination, or an
   individual legal act. Preserve legal references, amendments and transitional
   provisions. A field with a promising name alone is insufficient.
2. Represent historical and prospective versions without discarding older
   definitions. For a requested date, only select a definition when the source
   establishes it is applicable for that date and commodity; otherwise return
   an **undetermined** state rather than choosing the largest version number.
3. Compare proposed source revisions with the approved source, including
   removed rows and altered footnote/product exceptions. Independently
   examine prospective records and any legal ambiguities.
4. In a separate reviewed change, promote the verified source into the
   approved inputs, rebuild the PARAM map and model readings, and review
   regression tests and acceptance failures. Maintain a reproducible source
   snapshot and provenance.

The [DG SANTE developer documentation](https://developer.datalake.sante.service.ec.europa.eu/docs)
recommends explicitly pinning an API version. Changes to API versions need a
separate schema review.

**No automated workflow may silently promote a newer version of an RD as the
legally applicable one based solely on the API's record order or version.**
