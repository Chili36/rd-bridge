# Data provenance, reuse and attribution

The **software** in `rd_bridge/`, `tests/` (Python files), workflow files and
other original code is released under the [MIT license](LICENSE). **The
third-party data and documentation from which the reference JSON files are
derived are not covered by that software license.**

The project's original selection, normalization, evidence annotations and
mapping contributions in `data/` are offered under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
to the extent those contributions are protected and the contributors hold
the relevant rights. This does *not* purport to relicense European Commission,
EFSA or other third-party source material. Their reuse conditions continue
to apply; users should follow the linked source notices.

## Data sources

| File | Source and acknowledgment | Transformations |
|---|---|---|
| `data/residues_en.json` | European Commission, Directorate-General for Health and Food Safety (DG SANTE), [EU Pesticides Database v3](https://food.ec.europa.eu/plants/pesticides/eu-pesticides-database_en). [EU reuse policy](https://digital-strategy.ec.europa.eu/en/news/rules-reuse-commission-information) generally permits reuse with attribution, subject to exclusions. | Downloaded English residue rows, including historical versions exposed by the endpoint. |
| `data/active_substances.json` | European Commission, DG SANTE, `active-substances` endpoint from the same database. | API pagination, selection of relevant identification/status fields and exact duplicate removal. No change to the source's default-MRL wording. |
| `data/param_pest_terms.json`, `data/param_components.json` | **European Food Safety Authority (EFSA)**, PARAM catalogue, version 17.6 (valid from 2026-06-22), from [openefsa/efsa-catalogues](https://github.com/openefsa/efsa-catalogues); see the [EFSA legal notice](https://www.efsa.europa.eu/en/legalnotice). | Selection of reportable terms, associated identifiers, CAS and parent/term relationships. |
| `data/foodex2_ppp.json`, `tests/fixtures/` | **EFSA**, FoodEx2 food-class mapping documentation, [Zenodo concept record 3989602](https://zenodo.org/records/3989602); rules and 2020 reference test fixture extracted from EFSA's published package. | Rule subset and relevant food classification hierarchies selected for an open deterministic implementation. |
| `data/residue_param_map.json`, `data/unmatched.json`, `data/parts_comparison.json` | Derived from the EC and EFSA source datasets above and this project's matching, rule parsing and model-reading methods. | Definition-to-PARAM links, commodity exceptions, parts, confidence/evidence and diagnostics. |
| `data/model_parts.json` | Model-generated text-structure readings of European Commission residue definitions, grounded against EFSA PARAM terms. | Cached inputs/outputs; models are not authoritative legal or chemical sources. |

The project does not redistribute the original `.ecf` catalogue archive or the
raw Zenodo pesticide monitoring records. Published validation reports, if any,
are **derived aggregate statistics**, not a redistribution of reporting rows.

The dataset is a **derived, non-official** reference and must not be described
as being endorsed by the European Commission, EFSA or any contributing Member
State. The [EU Pesticides Database disclaimer](https://food.ec.europa.eu/plants/pesticides/eu-pesticides-database_en)
states that the database is informational and has no legal value; only the
applicable legislation has legal force. `rd-bridge` does **not** assess legal
compliance with maximum residue levels.

## How to cite

When redistributing or building upon this project, acknowledge:

- **rd-bridge contributors**, `rd-bridge`, reference dataset and mapping code,
  https://github.com/Chili36/rd-bridge (identify the commit and snapshot date);
- **European Commission, DG SANTE**, EU Pesticides Database (source EU
  pesticide-residue and active-substance definitions);
- **European Food Safety Authority (EFSA)**, PARAM and FoodEx2 catalogues
  (include the version of each EFSA source).

Indicate what you changed. Consult the upstream notices linked above for any
additional obligations or third-party rights. No use of official EU or EFSA
logos or implied endorsement is authorized by this project's license.
