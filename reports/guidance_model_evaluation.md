# Guidance-in-the-loop evaluation

Model: `claude-haiku-5-5`; prompt: `b8bb12e410942560`; guidance: `b4fb746047c944a8`.

This evaluates only explicit, preselected EU-text component checks. **Neither an overall accuracy measure nor an automatic approval.**

Baseline cached Haiku: **10/12** checks passed; guided: **12/12**.

Improved: chloridazon_animal, fenpyroximate_m3. Regressed: none.

| Case | Baseline | Guided | Guidance source IDs |
| --- | --- | --- | --- |
| chloridazon_animal | FAIL | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-COMMODITY-VARIANTS, EFSA-WHOLE-VS-PARTS |
| chloridazon_default | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| fenpyroximate_m3 | FAIL | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-COMMODITY-VARIANTS, EFSA-WHOLE-VS-PARTS |
| kresoxim_bf4909 | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-COMMODITY-VARIANTS, EFSA-WHOLE-VS-PARTS |
| captan_exception_thpi | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, OECD-COMMODITY-VARIANTS, EFSA-WHOLE-VS-PARTS |
| aldicarb_sum | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| methiocarb_sum | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| flonicamid_sum | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| ddac_homologues | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-SUMMED-COMPONENTS, OECD-FREE-CONJUGATED, EFSA-WHOLE-VS-PARTS |
| mevinphos_isomers | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-SUMMED-COMPONENTS, OECD-ISOMER-COVERAGE, EFSA-WHOLE-VS-PARTS |
| ester_pair | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| phorate_derivatives | PASS | PASS | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| dinocap_conditional | review | review | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, OECD-ISOMER-COVERAGE, EU-CONDITIONAL-CLAUSE, EFSA-WHOLE-VS-PARTS |
| guazatine_complex | review | review | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-SUMMED-COMPONENTS, EFSA-WHOLE-VS-PARTS |
| phosphane_generators | review | review | EU-TEXT-CONTROLS, OECD-ENFORCEMENT-SCOPE, OECD-EXPRESSION-BASIS, OECD-SUMMED-COMPONENTS, OECD-FREE-CONJUGATED, EFSA-WHOLE-VS-PARTS |

## Readings requiring review

### dinocap_conditional — RD 284

EU definition: Dinocap (sum of dinocap isomers and their corresponding phenols expressed as dinocap) (Where only meptyldinocap or its corresponding phenol are detected but none of the other components constituting dinocap (including their corresponding phenols), the MRLs and residue definition of meptyldinocap are to be applied.)

Guided extracted analytes: dinocap

### guazatine_complex — RD 321

EU definition: Guazatine (guazatine acetate, sum of components)

Guided extracted analytes: Guazatine

### phosphane_generators — RD 354

EU definition: Phosphane and phosphide salts (sum of phosphane and phosphane generators (relevant phosphide salts), determined and expressed as phosphane)

Guided extracted analytes: phosphane

## Provenance

Rule text, source location and source URL are versioned in [data/interpretation_guidance.json](../data/interpretation_guidance.json).
Complete prompt-response interpretation objects for every case are in [guidance_model_evaluation.json](guidance_model_evaluation.json).
No model results are accepted into the PARAM map by this experiment.

