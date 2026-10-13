# Updating the EU residue reference

## Applicability policy

**Use the latest EU-published residue definition as the currently applicable
definition unless we have specific evidence to the contrary.**

A missing application date does **not** mean an RD is invalid, and it does not
block a refresh. In resolver output, `applicability.status = "presumed_applicable"`
documents this working assumption; `status = "resolved"` remains a successful
PARAM lookup. No general "unverified" state is returned for missing dates.

If a source shows a future application date, that is a reason to investigate
**that particular revision** and retain the earlier applicable version.
Publication, entry into force and application can differ, as the
[European Commission's MRL Q&A](https://food.ec.europa.eu/plants/pesticides/maximum-residue-levels/qas-pesticides_en)
explains. The legal relationship of an MRL date to an RD may be
commodity-dependent; the date's meaning must be established before changing
selection. Missing or ambiguous dates are not a reason to reject the latest RD.

Historical `as-of` selection is not implemented; see [issue #6](https://github.com/Chili36/rd-bridge/issues/6).
The current data are a latest-version reference, not a historical legal archive.

## Weekly and manual updates

[Update EU reference data](../.github/workflows/eu_sources.yml) runs each
Monday 06:00 UTC, or on demand. It:

1. Fetches **every page and every field** returned by the DG SANTE v3
   `pesticide-residues` (English) and `active-substances` APIs.
2. Checks API response structure, pagination completeness and suspicious drops
   in record counts. A broken/empty API does not overwrite working data.
3. Saves the full raw source snapshots under `data/eu_sources/`, with a
   manifest containing source URLs, record/field counts, checksums and possible
   date fields. Duplicate source records are preserved in these snapshots.
4. Updates `data/residues_en.json` with the complete new residue records and
   `data/active_substances.json` with the existing resolver-compatible
   five-field index. All original active-substance fields remain in the
   full-source snapshot.
5. Uses the **committed EFSA PARAM 17.8** source snapshot (not an unversioned or potentially older ECF download) and rebuilds `data/residue_param_map.json`, uses cached/model readings when
   available (requests new readings if configured), compares interpretation
   results and runs unit tests.
6. Opens a **normal pull request**, containing the proposed updated inputs,
   derived mapping and a report with changes, possible future dates and
   test results. It never auto-merges.

The default is to **propose the refreshed source and mapping**. Application
dates do not need to be verified before the PR can be created or merged.
When specific evidence shows that a future RD is not yet applicable, review
that individual case before merging the proposed version.

Possible future-date records are listed in the refresh report whenever fields
such as `application_date` have future values. Field names alone are not
proof of legal applicability; these candidates are surfaced for investigation,
not used to reject an entire refresh.

To test locally (Python 3.10+; standard library):

```bash
python -m unittest discover -s tests -t .
python -m rd_bridge.eu_refresh --report eu-refresh-report.md
python -m rd_bridge.match
python -m rd_bridge.compare_parts
```

The comparison command intentionally returns exit status 3 when acceptance
cases fail. The workflow still creates the PR and includes that result.

## Data coverage and known limits

The project currently downloads **all fields from its two existing DG SANTE
endpoints**; this is not a copy of every table in the EU Pesticides Database.
Separate EU endpoints cover MRL values, product associations and MRL downloads.
These may be needed for authoritative application dates and transitions, and
are not integrated yet.

Our prior October 2026 residue snapshot contains eight fields and **no date
field**. The historical `active_substances.json` contains only five projected
fields. This refresh preserves new fields rather than discarding information
that may be useful for later date-aware interpretation.

[DG SANTE API documentation](https://developer.datalake.sante.service.ec.europa.eu/docs)
recommends pinning and reviewing API versions rather than automatically
following breaking changes. We pin `api-version=v3.0` and review new fields.

**Operating rule:** Assume the latest EU RD is applicable until specific
information establishes otherwise. Review those exceptions, not every
un-dated definition.

## PARAM catalogue version

The PARAM input is currently version **17.8** (valid from 2026-09-11), imported from an EFSA Catalogue Browser Excel export. Its SHA-256 is recorded in `data/param_components.json`. The original workbook is intentionally not committed. To import an updated official export, run `python -m rd_bridge.fetch_param PARAM_17.8.xlsx` locally, then regenerate the residue map and run the regression suite. The default remote ECF fetch refuses to downgrade this version.
