# rd-bridge

**rd-bridge is a reference dataset for EU pesticide residue definitions and their EFSA PARAM codes.**

It has **two core jobs**:

1. **Track the current EU residue definitions.** For each pesticide, preserve what its residue definition includes—the whole residue, its identifiable parts, and any definitions that apply to particular products or product groups.
2. **Map those definitions to EFSA PARAM.** Identify the PARAM code for each whole residue definition and, where possible, the PARAM codes of its constituent parts. Record the evidence and leave uncertain links explicit.

**The product is [`data/residue_param_map.json`](data/residue_param_map.json).** It is a versioned snapshot of the reference data, not primarily a food lookup service.

## 1. Track residue definitions and the products they apply to

A pesticide does **not** necessarily have one residue definition for all food products. EU law can specify a different residue definition for a product or group of products.

The EU Pesticides Database provides the definitions and their commodity-specific exceptions. rd-bridge records:

- The **default definition**, used where no commodity exception applies.
- Any **product-specific definitions**, identified by EU **Annex I commodity codes** (including relevant exclusions).
- The wording of each definition, its source version and the parts of a sum.

**A definition's product scope is expressed in EU Annex I terms. It is not expressed as a FoodEx2 code.** An Annex I group code can apply to many individual products.

For example, **acetamiprid** has:

| Applicable product scope | Residue definition | Whole-residue PARAM code |
|---|---|---|
| Default, where no exception applies | Acetamiprid | `RF-0014-001-PPP` |
| Animal products (`1000000`), except `1040000` | Sum of acetamiprid and N-desmethyl-acetamiprid (IM-2-1), expressed as acetamiprid | `RF-00003326-PAR` |

The product-dependent distinction already exists in the **EU residue definitions**, before FoodEx2 enters the picture.

## 2. Map each definition and its parts to EFSA PARAM

EU residue definitions tell us **what constitutes the residue**. EFSA PARAM supplies **codes used to report substances and residue definitions**. Neither source provides a complete, maintained public bridge between the two.

rd-bridge constructs that bridge. It maps:

- **The whole definition (the sum)** to its PARAM code.
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

## Where FoodEx2 comes in: **using** the dataset

**FoodEx2 is not a source of residue definitions and is not needed to map them to PARAM.** It enters only when we start with a **particular food sample** and need to select which product-specific definition applies.

The optional lookup follows this sequence:

```text
FoodEx2 code of a sampled food
    ↓ EFSA food-class mapping rules
EU Annex I commodity code
    ↓ select the applicable default or product-specific definition
EU residue definition for that product
    ↓ rd-bridge's definition → PARAM link
PARAM code of the complete residue definition
```

For example, FoodEx2 code `A02LV` (cow milk) maps to Annex I commodity `1020010`. The applicable **thiabendazole** definition is the milk exception for group `1020000`; its whole-residue PARAM code is `RF-00007630-PAR`.

```bash
python -m rd_bridge.resolve A02LV thiabendazole
```

The FoodEx2 classification selects **which existing definition applies**; it does not create a new definition or change its chemical parts. If the food cannot be placed in an Annex I category and the substance has exceptions, `resolve` returns candidate definitions rather than guessing.

**For an overview of today's residue definitions and their PARAM codes, FoodEx2 is not involved at all.** It is a downstream convenience, not a third core objective.

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

- The committed data describes **current** residue definitions as retrieved for the October 2026 snapshot. It does **not** select historic definitions using a sampling date. Refreshes are manual.
- Some definitions or parts have no trustworthy PARAM link; the dataset records those limitations. Substance approval status and default-MRL information can come from the separate active-substances source, but rd-bridge does **not** assess MRL compliance.
- FoodEx2-to-Annex I mapping is limited to supported EFSA food-class rules. It may not resolve processed or composite foods.
- [Comparison with accepted Swedish and French 2024 reports](reports/monitoring_2024.md) found 99.98% agreement among **judgeable full-definition (`P005A`)** records. This is conditional agreement with accepted reporting, **not proof of legal correctness or independent mapping accuracy**. The [machine-readable results](reports/monitoring_2024.json) preserve the denominator and disagreements.

## Sources, reuse and documentation

The definitions come from the **European Commission's EU Pesticides Database**; the PARAM codes and FoodEx2 rules come from **EFSA**. The mapping in this repository is a derived, non-official reference. The software is [MIT licensed](LICENSE); see [data provenance and reuse conditions](DATA_SOURCES.md) for upstream acknowledgments and licenses.

Further documentation: [mapping methods](docs/MAPPING_METHOD.md), [2024 validation and limitations](reports/monitoring_2024.md), and the [historical release review](reports/PUBLICATION_REVIEW_2026-10-11.md).
