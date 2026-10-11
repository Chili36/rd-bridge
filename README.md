# rd-bridge

**A reference dataset of current EU pesticide residue definitions, each definition's sum and constituent parts, and their EFSA PARAM codes.**

The product is [`data/residue_param_map.json`](data/residue_param_map.json). For each currently published EU residue definition, it records the PARAM term for the whole residue, the terms for identifiable parts, and any commodity-specific `(R)` exceptions. Links retain their matching method and evidence; missing or ambiguous links remain explicit rather than being guessed.

## A dataset entry

For example, acetamiprid has a default definition for plants and a different summed definition for most animal products. This is an excerpt from residue `10` (some metadata and evidence fields omitted):

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

`default` and each `exceptions` entry have a `definition`, a whole-residue `param_codes` link, and `components` for its parts. The full row also preserves the raw footnote, the definition version, the source of the component reading, and any ambiguities or repairs.

## Using the dataset

`resolve(food, substance)` is **one application** of the dataset, not the reason it exists. It uses EFSA's FoodEx2 food-class rules to select the applicable Annex I commodity and therefore the right definition. It does not decide whether a reported result is legally compliant.

```bash
$ python -m rd_bridge.resolve A02LV thiabendazole  # cow milk
{"status": "resolved", "scope": "exception", "method": "exact",
 "param_codes": ["RF-00007630-PAR"], "...": "other fields omitted"}
```

Analysis completeness (`--analysed`) is a separate, optional diagnostic built on the same component data. It indicates which known parts were covered; it is not a compliance decision and must not be read as proof that every chemically possible form was measured.

## Why this bridge is needed

The EU publishes residue definitions but not their EFSA PARAM links. EFSA publishes PARAM but not a maintained public link from each EU definition to its PARAM code. A residue's definition can also change by commodity:

| Substance | Default (plant) | Exception |
|---|---|---|
| Acetamiprid | `RF-0014-001-PPP` | animal products (1000000 except 1040000): `RF-00003326-PAR` |
| 2-phenylphenol | `RF-00007633-PAR` (sum with conjugates) | animal products: `RF-0823-001-PPP` (parent only) |
| Thiabendazole | `RF-0416-001-PPP` | animal products: `RF-00007629-PAR`; milk (1020000): `RF-00007630-PAR` |

## How it's built

```
EU Pesticides Database ──current residue definitions and (R) exceptions──▶ definitions
EFSA PARAM ───────────────whole terms, component terms and hierarchies─▶ PARAM codes
Deterministic matching ──with optional cached model readings─────────▶ residue_param_map.json
EFSA FoodEx2 rules ───────food class → Annex I commodity──────────────▶ resolve()
```

Every link records whether it was exact, a deterministic normalization, a model-supported component choice, ambiguous, or unmatched. The model reads the *parts of the text*; it is not a substitute for EU definitions or EFSA's catalogue. The committed model readings are an input to rebuilding the reference data, not a live dependency of `resolve`.

## Components and their evidence

```
Sum of acetamiprid and N-desmethyl-acetamiprid (IM-2-1), expressed as acetamiprid
  summed code  RF-00003326-PAR
  parts        acetamiprid       RF-0014-001-PPP   (family)
               IM-2-1            RF-00002836-PAR   (family)
```

Each definition carries `components`: every part with its role (`analyte`; `group` for parts
that cannot be listed one by one, such as "all metabolites containing the 3,5-dichloroaniline
moiety"), its PARAM code(s) and how they were found. Qualifiers ("its salts", "conjugates",
E/Z isomers) are preserved as notes, not as extra required analyses. Named, reportable
PARAM forms covered by "its esters/salts/conjugates" are recorded under
`qualifier_components`, with method `qualifier` and the matching evidence. This is
a conservative subset, **not** an exhaustive list of possible chemical forms. Parts
explicitly named in the EU definition are matched in order of evidence:

| method | where the part was found in PARAM |
|---|---|
| `param_sum` | filed under the definition's own summed PARAM term |
| `family` | in the PARAM family of the substance the residue is expressed as |
| `global` | anywhere among pesticide terms, by full name |
| `global_code` | anywhere, by a code only one term carries (THPI, BH 518-2); never by metabolite numbers such as M4 |
| `definition` | a single-substance definition: its own link |
| `model` | the rules found nothing; the model named this family term (see Model readings) |
| `param_hierarchy` | documented component directly under a trusted PARAM whole, independently verified |
| `scientific_definition` | a published EFSA definition establishes a constituent not filed directly under the whole in PARAM |
| `qualifier` | a named PARAM ester/salt/conjugate covered by EU wording (stored separately) |
| `none` | no PARAM term (e.g. TFNG) |

```bash
$ python -m rd_bridge.resolve A01QX acetamiprid --analysed RF-0014-001-PPP
"completeness": {"status": "partial",
  "covered": [{"name": "acetamiprid", "param_codes": ["RF-0014-001-PPP"]}],
  "missing": [{"name": "N-desmethyl-acetamiprid (IM-2-1)", "param_codes": ["RF-00002836-PAR"]}]}
```

For example, the EU definition **Pyrethrins** is only one word, but EFSA's 2024
residue-definition review identifies six analytes. Pyrethrin I/II and Jasmolin I/II
use `param_hierarchy` evidence; Cinerin I/II use `scientific_definition`,
because PARAM files them under Cinerin. Every such mapping includes source links.
A substance named with "including" (dichlorprop including dichlorprop-P, benalaxyl including
benalaxyl-M) is a part with `covered_by`: measuring the including substance covers it too. One
named inside a qualifier group (quizalofop's esters, including propaquizafop) is a required part.

`completeness` is `complete` (the summed code, or every part, was analysed), `partial` (with
what is missing), `undetermined` (everything with a PARAM code was analysed; the rest has none
or is a group) or `not_covered`.

`status` is `resolved`, `untrusted_link` (a `near` match), `no_param_link`, `ambiguous_param`,
`ambiguous_exception`, `commodity_unresolved` (EFSA places the food in no Annex I class and the residue has
commodity exceptions: all candidates are returned, none is guessed), `unknown_substance` or
`ambiguous_substance`. `no_residue_definition` identifies an EU-known substance
for which the API explicitly states a default MRL; `residue_definition_unresolved`
identifies a named substance whose linked definition could not be selected.
These statuses do not assess compliance.

## Build and test

Python 3.10+, standard library only (falls back to `curl` where Python's TLS check fails).

```bash
python -m rd_bridge.fetch_residues                       # -> data/residues_en.json
python -m rd_bridge.fetch_active_substances              # -> data/active_substances.json
python -m rd_bridge.fetch_param [PARAM.ecf]              # -> data/param_pest_terms.json, data/param_components.json
python -m rd_bridge.model_parts                          # -> data/model_parts.json (needs ANTHROPIC_API_KEY)
python -m rd_bridge.match                                # -> data/residue_param_map.json, data/unmatched.json
python -m rd_bridge.compare_parts                        # report on the model readings -> data/parts_comparison.json
python -m rd_bridge.foodex2_mapping [package.zip]        # -> data/foodex2_ppp.json (needs pandas)
python -m rd_bridge.commodity A01DJ                      # sampMatCode -> food class, Annex I code
python -m rd_bridge.resolve A01DJ acetamiprid            # sampMatCode + substance -> PARAM code
python -m unittest discover -s tests -t .                # tests
python -m scripts.validate_monitoring --countries SE FR  # public Zenodo 2024 reports; Python 3.12+
```

`foodex2_mapping` downloads the latest EFSA package from Zenodo when no zip is given. It reads
EFSA's SAS rule table (pandas) and SAS format catalog (`rd_bridge/sas7bcat.py`) and keeps only
what the pesticide rules read: rules, implicit facets, and the parents of each term in the
hierarchies the rules use. Everything else stays standard library.

`fetch_param` downloads EFSA's PARAM catalogue from github.com/openefsa/efsa-catalogues (public,
updated every few months, no account needed) and extracts it with `load_param`; a local
`PARAM.ecf` skips the download. The `.ecf` itself is not committed.

The model step is optional: without its cache `match` uses the rule parser only. In CI it runs
in the **Model readings** workflow (Actions tab, run by hand on `main`, with a choice of model:
Haiku 5.5 by default or Sonnet 5.5; locally `RD_BRIDGE_MODEL`), which reads the key
from the repository secret `ANTHROPIC_API_KEY`, rebuilds the map, runs `compare_parts` and opens
a PR with the result. It never runs on pull requests.

## Model readings

First the components, then the mapping.

1. **Components.** A model (`claude-haiku-5-5` by default, `model_parts`) reads each definition into
   components: analytes, groups, qualifiers, `expressed_as`, and `included_in` for "X including
   Y". This replaces the rule parser, whose regexes kept missing phrasing.
2. **Mapping.** Each component is mapped to PARAM by the rules, as before: the definition's
   summed term in PARAM's hierarchy, the substance's family, then the whole catalogue by name.
   A model-read name is only linked if it is built from words of the definition, and an
   "included in" is only used where the definition says "including"; a misread stays unlinked.
   Only when the rules find nothing does the model's answer count: the prompt lists the PARAM
   terms in the substance's family, and the model may name the one a component is. That link
   has method `model`; it is used, never queued for review, and always visible as a model choice.
   Per definition, the model's reading is used only if it keeps every code the rules link
   there; otherwise the rule reading stays and `model_reading_lost` lists what would have been
   lost. Where the rules see one substance, a model reading that lists linked components instead
   (benzalkonium chloride -> BAC 8 ... BAC 18) loses nothing.
3. **Measuring.** Where the rules map a component and the model named a term too, both answers
   are kept (`model_agrees`). How often they agree is what the `model` links are trusted on.

Answers are cached in `data/model_parts.json` per definition, with the model, a hash of the
prompt and a hash of the family names offered: a changed definition, prompt, model or family is
asked again, the rest is reused. Each definition says where its components came from
(`parts_from`: `model`, `rules` or `published_evidence`).

`compare_parts` reports, for the PR the workflow opens: how many readings give the same result
as the rule parser, the agreement count, every `model` link, and acceptance cases either reader
must pass (the methyl ester of 2,5-dichlorobenzoic acid, the BAC and DDAC chain lengths, and
earlier regressions; the rule parser fails 4 of 12).

## Output

`data/residue_param_map.json`, one row per current residue definition:

- `default`: the definition and its link (`method`, `param_codes`)
- `exceptions`: each `(R)` footnote exception with `commodity_codes`, `except_codes`,
  `definition`, its link, `repairs` (commodity-code typos fixed, with the reason) and `issues`
  (structural doubts: unknown Annex I group, an except code outside every included code)
- `components` on the default and on each exception: its parts (see above)
- `qualifier_components`: PARAM-named parts covered by a general ester/salt/conjugate qualifier
- `footnote_r`: the raw footnote text, kept on every row

`method` says how a link was made, most trusted first. Every method beyond `exact` writes its
`evidence` (the PARAM name it hit, plus what made the hit):

| method | rule |
|---|---|
| `exact` | normalised text equal |
| `spelling` | equal after a fixed spelling table (sulph/sulf, phtal/phthal, -ine/-in, -ole/-ol, desethyl/de-ethyl, "strain", "aka", "&") |
| `compound_set` | same set of summed components and same anchor (the parent, from "expressed as", the head, or the first component), against `pestClass=RD` terms |
| `cas` | a CAS number written in the EU name equals the PARAM term's CAS |
| `alias` | a lab code (`BAS 670H`), `aka` name, E-number or category prefix in the definition, or a code alias on the PARAM side (`(DMST)`); a stated CAS that differs vetoes it |
| `ambiguous` | one of the above hit more than one PARAM code |
| `near` | fuzzy ≥ 0.9 **and** the same parent substance; plausible, not trustworthy as-is |
| `none` | no link; a fuzzy hit on a different parent (Ipconazole → Penconazole) is kept as `evidence.rejected` |

## Snapshot and known limits (data snapshot 2026-10-11)

684 current residues, 77 with commodity exceptions, 767 definitions: **601 exact links (78%)**,
625 by deterministic methods (81%), 6 near suggestions and 136 unmatched. Many unmatched
definitions are biologicals and basic substances without a reportable `pestParam` term.
Model readings are **already committed**: 751 of 767 definition entries use them,
15 use the rule reading and one (Pyrethrins) uses independent published evidence.

Against EFSA's 2024 accepted pesticide reports for
[Sweden](https://zenodo.org/records/20036095) and
[France](https://zenodo.org/records/20034822), the **P005A** results
(reported as fully analysed legal residue definitions) agree with today's
selected PARAM code in **1,410,070 of 1,410,330 judgeable results (99.98%)**:
99.79% in Sweden, 99.99% in France. The 260 differences may reflect
historical definitions or other reporting discrepancies; they are **not**
proven errors in either the reference dataset or laboratories' reports.
After the qualifier/active-substance extensions, 194,240 previously
unrecognized report rows now have identifiable candidate links, some
ambiguous. See the [validation methodology and figures](reports/monitoring_2024.md),
[machine-readable aggregates](reports/monitoring_2024.json), and
[reproducible validator](scripts/validate_monitoring.py).

**Agreement with accepted reporting is not proof of legal or chemical
correctness.** Candidate residues are partly identified using the reported
PARAM code itself, so the 99.98% is a *conditional concordance measure*,
not independently measured lookup accuracy or a compliance decision.
`P002A` (part of a sum), `P004A` (subset sum), and unknown `paramType`
must not be treated as reports of fully analysed current definitions.

Known limitations before public release:

- **Current definitions only.** There is no sampling-date lookup. Metalaxyl in 2024 animal
  products and the earlier phosmet oxon definition illustrate why historical reporting
  can disagree with today's definition ([#25](https://github.com/Chili36/rd-bridge/issues/25)).
- **Qualified components are a conservative subset.** The name-based mapping covers
  explicitly identifiable ester/salt/conjugate PARAM terms, not every chemically possible
  derivative.
- **Active substances are a separate source.** The EU index and fallback can identify
  a substance without a specific residue definition, but cannot infer one when the
  API points to another differently named definition.
- **No scheduled refresh.** The build uses a snapshot; input refreshes and model readings
  are manual ([#4](https://github.com/Chili36/rd-bridge/issues/4)).
- **FoodEx2 mapping.** Exception codes are checked against Annex I structure, not the full
  Annex I code list. Against EFSA's packaged 2020 test output without hierarchy expansion,
  the port agreed on 2,761 of 2,787 codes. With hierarchy expansion, 2,652 of those
  codes reach an Annex I code versus 493 in that old output. Bare FoodEx2 terms:
  4,075 of 31,692 reach Annex I; others may be composites, processed foods or special classes.
- **2024 full-definition discrepancies remain unexplained.** The repeatable
  `P005A` comparison found 90 Swedish and 170 French differences, covering
  12 grouped PARAM-code combinations; this is **not** evidence of 260 mapping errors.
  All twelve combinations, their counts and both codes are in
  [the validation findings](reports/monitoring_2024.md#every-full-definition-disagreement-p005a-grouped).
  Historical applicability remains [#25](https://github.com/Chili36/rd-bridge/issues/25).

## Sources

- EU Pesticides Database API v3.0 (European Commission, DG SANTE), CC BY 4.0:
  `https://api.datalake.sante.service.ec.europa.eu/sante/pesticides/pesticide-residues?format=json&pesticide_residue_lg=EN&api-version=v3.0`
- EFSA PARAM catalogue, version 17.6 (2026-06-22), from github.com/openefsa/efsa-catalogues:
  `data/param_pest_terms.json` (approved, reportable `pestParam` terms, for linking definitions)
  and `data/param_components.json` (every approved `pestParam` term including the COMPONENTS
  group, with names, CAS and PARAM-hierarchy families).
- EFSA, "Food classification mapping for legal limit compliance of chemical monitoring data",
  Zenodo concept record 3989602, v4 (doi:10.5281/zenodo.20490648), CC BY 4.0. The extract is
  `data/foodex2_ppp.json`; `tests/fixtures/` holds its 2020 rule table and test output. The
  package itself (99 MB zip, 1 GB SAS catalog) is not committed.

## License and provenance

Code: [MIT](LICENSE). The mapping data combines original annotations with EU and EFSA
source material, which retains its own reuse conditions. See [DATA_SOURCES.md](DATA_SOURCES.md)
for licensing boundaries, acknowledgments and citations. This is **not** an official
European Commission or EFSA dataset, and it does not determine MRL compliance.

## Public-release review

The dated [pre-publication findings and decision record](reports/PUBLICATION_REVIEW_2026-10-11.md)
covers implementation decisions, reproduced SE/FR results, scientific evidence,
source reuse, the full-history security scan and remaining publication conditions.
[Issue #35](https://github.com/Chili36/rd-bridge/issues/35) tracks the unresolved
decision about exposing historical commit metadata before making the repository public.
