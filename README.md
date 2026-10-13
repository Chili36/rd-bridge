# rd-bridge

**rd-bridge maps EU-published pesticide residue definitions—including which products they apply to—to EFSA PARAM codes.**

It has two core tasks:

1. **Track residue definitions.** Record the current definition for each pesticide, what substances it includes, and which products or product groups each definition applies to.
2. **Map definitions to PARAM.** Link each whole residue definition and its identifiable constituent parts to EFSA PARAM codes, retaining evidence and flagging uncertain links.

The result is [`data/residue_param_map.json`](data/residue_param_map.json), a versioned reference dataset.

## 1. Track residue definitions and the products they apply to

EU residue definitions can differ by product or product group. The same pesticide may have one definition for plant products and another for animal products.

The EU Pesticides Database provides the definitions and their commodity-specific exceptions. rd-bridge records:

- The **default definition**, used where no commodity exception applies.
- Any **product-specific definitions**, identified by EU **Annex I commodity codes** (including relevant exclusions).
- The wording of each definition, its source version and the parts of a sum.

Product scope is expressed using **EU Annex I commodity codes**. One code may represent a group of products.

For example, **acetamiprid** has:

| Applicable product scope | Residue definition | Whole-residue PARAM code |
|---|---|---|
| Default, where no exception applies | Acetamiprid | `RF-0014-001-PPP` |
| Animal products (`1000000`), except `1040000` | Sum of acetamiprid and N-desmethyl-acetamiprid (IM-2-1), expressed as acetamiprid | `RF-00003326-PAR` |

## 2. Map each definition and its parts to EFSA PARAM

EU residue definitions tell us **what constitutes the residue**. EFSA PARAM supplies **codes used to report substances and residue definitions**. Neither source provides a complete, maintained public bridge between the two.

rd-bridge constructs that bridge. It maps:

- **The whole definition** (a single substance or a sum) to its PARAM code.
- **The named constituents**, when they have PARAM codes, to their own codes.
- **Additional identifiable forms** covered by wording such as “its esters” or “its salts,” with that qualifier recorded as evidence rather than treated as an exhaustive list.

For the acetamiprid animal-product definition, the data looks like this (excerpt; omitted fields are described below):

```json
{
  "residue_id": 10,
  "name": "Acetamiprid (R)",
  "default": {
    "definition": "Acetamiprid",
    "method": "exact",
    "param_codes": ["RF-0014-001-PPP"]
  },
  "exceptions": [{
    "commodity_codes": ["1000000"],
    "except_codes": ["1040000"],
    "definition": "Sum of acetamiprid and N-desmethyl-acetamiprid (IM-2-1), expressed as acetamiprid",
    "method": "exact",
    "param_codes": ["RF-00003326-PAR"],
    "components": [
      {"name": "acetamiprid", "role": "analyte", "method": "family", "param_codes": ["RF-0014-001-PPP"]},
      {"name": "N-desmethyl-acetamiprid (IM-2-1)", "role": "analyte", "method": "family", "param_codes": ["RF-00002836-PAR"]}
    ]
  }]
}
```

Each default or exceptional definition has its own `definition`, whole-residue `param_codes` and, when identifiable, `components`. The full record also includes source version, original footnote text, match method and evidence, and any unresolved ambiguities. A missing code is not silently guessed.

## Looking up a definition for a food

When a sampled food has a **FoodEx2 code**, `resolve` uses EFSA's food-class mapping rules to find its **EU Annex I commodity code**. That code selects the applicable residue definition and its PARAM code from the reference dataset.

```text
FoodEx2 code → EU Annex I commodity → applicable residue definition → PARAM code
```

For example, FoodEx2 code `A02LV` (cow milk) maps to Annex I commodity `1020010`. This falls under the milk group `1020000`, for which **thiabendazole** has a specific residue definition. Its whole-residue PARAM code is `RF-00007630-PAR`.

```bash
python -m rd_bridge.resolve A02LV thiabendazole
python -m rd_bridge.resolve A02LV RF-0416-001-PPP   # or by a whole-residue PARAM code
```

If a food cannot be assigned to an Annex I commodity and a pesticide has product-specific exceptions, `resolve` returns the candidate definitions rather than guessing.

## What's included

| Data or function | Role |
|---|---|
| [`data/residue_param_map.json`](data/residue_param_map.json) | **The primary reference dataset:** current definitions, product scopes, summed codes, parts, evidence |
| [`data/residues_en.json`](data/residues_en.json) | Source snapshot from the EU Pesticides Database |
| [`data/param_pest_terms.json`](data/param_pest_terms.json) and [`data/param_components.json`](data/param_components.json) | EFSA PARAM terms and component/hierarchy information used for matching |
| [`data/active_substances.json`](data/active_substances.json) | EU-known active substances, including those without a specific residue definition |
| [`data/foodex2_ppp.json`](data/foodex2_ppp.json) | **Optional lookup layer:** EFSA FoodEx2 → EU Annex I commodity |
| [`rd_bridge/resolve.py`](rd_bridge/resolve.py) | Uses a FoodEx2 food and pesticide to select a definition and its PARAM link |
| `--analysed` | **Optional diagnostic:** compares supplied PARAM codes against identifiable parts; not a compliance decision |

## Building and checking the reference

Python 3.10+; the core mapping uses the standard library. Some source extraction requires additional packages.

```bash
python -m rd_bridge.fetch_residues          # EU pesticide residue definitions
python -m rd_bridge.fetch_active_substances # EU active-substance index
python -m rd_bridge.fetch_param              # EFSA PARAM data
python -m rd_bridge.match                    # rebuild the primary JSON reference
python -m unittest discover -s tests -t .    # regression tests
```

Model-assisted reading of definition text is optional and cached in `data/model_parts.json`; link evidence remains visible. See [how the mapping works](docs/MAPPING_METHOD.md) for component interpretation, matching methods, model readings and reproducibility.

### Scope and limits

- The reference uses the **latest available EU-published residue definitions**, presumed applicable unless specific evidence shows a later application date. `resolve` reports `applicability.status = "presumed_applicable"`; it does not yet support selecting historical definitions by a sampling date.
- [EU source updates](docs/EU_SOURCE_REFRESH.md) fetch full source records, rebuild the PARAM map and propose updates through a pull request. Missing application dates do **not** prevent an update; known future-effective cases can be reviewed separately.
- Some definitions or parts have no trustworthy PARAM link; the dataset records those limitations. Substance approval status and default-MRL information can come from the separate active-substances source, but rd-bridge does **not** assess MRL compliance.
- The optional food lookup uses the supported EFSA food-class rules; some processed or composite foods may not map to an Annex I commodity.
- [Comparison with accepted Swedish and French 2024 reports](reports/monitoring_2024.md) found 99.98% agreement among **judgeable full-definition (`P005A`)** records. This is conditional agreement with accepted reporting, **not proof of legal correctness or independent mapping accuracy**. The [machine-readable results](reports/monitoring_2024.json) preserve the denominator and disagreements.

## Sources, reuse and documentation

The **European Commission's EU Pesticides Database** provides the residue definitions and their product scopes. **EFSA's PARAM catalogue** provides the reporting terms and codes. rd-bridge connects these sources into a derived, non-official reference. The software is [MIT licensed](LICENSE); see [data provenance and reuse conditions](DATA_SOURCES.md) for upstream acknowledgments and licenses.

Further documentation: [mapping methods](docs/MAPPING_METHOD.md) and [2024 validation and limitations](reports/monitoring_2024.md).
