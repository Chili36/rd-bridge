# Full guidance-based RD reinterpretation

**The independent gold-standard dataset requested previously does not exist and is not a prerequisite for this migration.** Interpretations are replaced using the best available EU wording, versioned OECD/EFSA guidance and reproducible automated checks.

- Model: `claude-haiku-5-5`; guidance version: `b4fb746047c944a8`
- **765 unique EU definition texts** have guidance-versioned interpretations.
- Definitions in whole-RD map: 767; whole-RD PARAM codes retained unchanged.
- Active component interpretations by source: {'guided_model': 735, 'legacy_regression_fallback': 2, 'legal_guidance': 1, 'published_evidence': 1, 'rules': 28}.
- Alternative model or source-literal fallbacks: 6.
- Entries whose analyte/group interpretation changed: **111**.
- Existing acceptance scenarios: **34/34 passed**.
- Model-vs-rule comparisons remaining: 47.

A passed acceptance test is not proof of legal compliance. Real source and PARAM consistency checks are retained; uncertainty is documented and improved iteratively, without waiting for an unavailable manual reference corpus.

## Changes to previously assigned component PARAM codes

| RD ID | Removed PARAM codes | Added PARAM codes |
| ---: | --- | --- |

## Model fallback provenance

These were not Haiku interpretations and are never concealed:

- **Benthiavalicarb-isopropyl (sum of benthiavalicarb-isopropyl (KIF 230 R-L) and its RS enantiomer (KIF 230-S-D))**: legacy_retained_after_regression; model: claude-haiku-5-5 (old cache).
- **Cinidon-ethyl (sum of cinidon ethyl and its E-isomer)**: guided_validation_repair; model: claude-sonnet-5-5.
- **Clethodim (sum of Sethoxydim and Clethodim including degradation products calculated as Sethoxydim)**: guided_validation_repair; model: claude-sonnet-5-5.
- **Fluvalinate (sum of isomers) resulting from the use of tau-fluvalinate**: legacy_retained_after_regression; model: claude-haiku-5-5 (old cache).
- **Guazatine (guazatine acetate, sum of components)**: guided_validation_repair; model: claude-sonnet-5-5.
- **Verticillium albo-atrum isolate WCS850**: model; model: claude-sonnet-5-5.
| 284 | RF-00002838-PAR | — |
| 301 | RF-0186-001-PPP | RF-00005723-PAR |
| 332 | — | RF-00013459-PAR, RF-0118-001-PPP, RF-0790-001-PPP |
| 354 | RF-00005719-PAR | — |
| 776 | RF-0107-001-PPP | RF-00007590-PAR |
| 776 | — | RF-00007590-PAR |

## Failed existing acceptance scenarios

None.

## All changed component interpretations

### RD 3: 1,2-dichloroethane (ethylene dichloride)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '1,2-dichloroethane', ('RF-0003-001-PPP',))

After:

- ('analyte', '1,2-dichloroethane (ethylene dichloride)', ('RF-0003-001-PPP',))

### RD 13: Aldrin and Dieldrin (Aldrin and dieldrin combined expressed as dieldrin)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Aldrin', ('RF-0021-002-PPP',))
- ('analyte', 'Dieldrin', ('RF-0021-003-PPP',))

After:

- ('analyte', 'aldrin', ('RF-0021-002-PPP',))
- ('analyte', 'dieldrin', ('RF-0021-003-PPP',))

### RD 18: Azimsulfuron

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Azimsulfuron', ('RF-0031-001-PPP',))

After:

- ('analyte', 'azimsulfuron', ('RF-0031-001-PPP',))

### RD 32: Bromopropylate

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Bromopropylate', ('RF-0052-001-PPP',))

After:

- ('analyte', 'bromopropylate', ('RF-0052-001-PPP',))

### RD 36: captan

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'captan', ('RF-0061-001-PPP',))

After:

- ('analyte', 'captan', ('RF-0061-001-PPP',))
- ('analyte', 'tetrahydrophthalimide (THPI)', ())

### RD 60: Clofentezine

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Clofentezine', ('RF-0098-001-PPP',))

After:

- ('analyte', 'clofentezine', ('RF-0098-001-PPP',))

### RD 69: Deltamethrin (cis-deltamethrin)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Deltamethrin', ('RF-0120-001-PPP',))

After:

- ('analyte', 'Deltamethrin (cis-deltamethrin)', ('RF-0120-001-PPP',))

### RD 74: Dicofol (sum of p, p´ and o,p´ isomers)

Previous: `model`; new: `rules`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'o,p´-dicofol', ('RF-0130-003-PPP',))
- ('analyte', 'p,p´-dicofol', ('RF-0130-002-PPP',))

After:

- ('analyte', 'o,p´-Dicofol', ('RF-0130-003-PPP',))
- ('analyte', 'p,p´-Dicofol', ('RF-0130-002-PPP',))

### RD 78: Dinoterb (sum of dinoterb, its salts and esters, expressed as dinoterb)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Dinoterb', ('RF-0145-001-PPP',))

After:

- ('analyte', 'dinoterb', ('RF-0145-001-PPP',))

### RD 83: Dithiocarbamates (dithiocarbamates expressed as CS2, including maneb, mancozeb, metiram, propineb, thiram and ziram)

Previous: `model`; new: `rules`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Dithiocarbamates', ('RF-0151-001-PPP',))

After:

- ('analyte', 'dithiocarbamates', ('RF-0151-001-PPP',))

### RD 92: Etoxazole

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Etoxazole', ('RF-0169-001-PPP',))

After:

- ('analyte', 'etoxazole', ('RF-0169-001-PPP',))

### RD 96: Fenarimol

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fenarimol', ('RF-0174-001-PPP',))

After:

- ('analyte', 'fenarimol', ('RF-0174-001-PPP',))

### RD 99: Fenhexamid

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fenhexamid', ('RF-0179-001-PPP',))

After:

- ('analyte', 'fenhexamid', ('RF-0179-001-PPP',))

### RD 103: Fentin (fentin including its salts, expressed as triphenyltin cation)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fentin', ('RF-0687-001-PPP',))

After:

- ('analyte', 'fentin', ('RF-0687-001-PPP',))

### RD 105: Fenvalerate (any ratio of constituent isomers (RR, SS, RS & SR) including esfenvalerate)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'esfenvalerate', ('RF-0690-003-PPP',))
- ('analyte', 'fenvalerate', ('RF-0690-002-PPP',))

After:

- ('analyte', 'Fenvalerate', ('RF-0690-002-PPP',))
- ('analyte', 'esfenvalerate', ('RF-0690-003-PPP',))

### RD 107: Flazasulfuron

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flazasulfuron', ('RF-0193-001-PPP',))

After:

- ('analyte', 'flazasulfuron', ('RF-0193-001-PPP',))

### RD 109: Flucythrinate (flucythrinate including other mixtures of constituent isomers (sum of isomers))

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flucythrinate', ())

After:

- ('analyte', 'flucythrinate', ())

### RD 113: Fluroxypyr (sum of fluroxypyr and its salts, expressed as fluroxypyr)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fluroxypyr', ('RF-0215-003-PPP',))

After:

- ('analyte', 'fluroxypyr', ('RF-0215-003-PPP',))

### RD 113: Fluroxypyr (sum of fluroxypyr, its salts, its esters, and its conjugates, expressed as fluroxypyr)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fluroxypyr', ('RF-0215-003-PPP',))

After:

- ('analyte', 'fluroxypyr', ('RF-0215-003-PPP',))

### RD 126: Hexaconazole

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Hexaconazole', ('RF-0241-001-PPP',))

After:

- ('analyte', 'hexaconazole', ('RF-0241-001-PPP',))

### RD 127: Hydrogen cyanide (cyanides expressed as hydrogen cyanide)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Hydrogen cyanide (cyanides expressed as hydrogen cyanide)', ('RF-0243-001-PPP',))

After:

- ('analyte', 'cyanides', ('RF-0243-001-PPP',))

### RD 130: Imazamox (Sum of imazamox and its salts, expressed as imazamox)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Imazamox', ('RF-0247-001-PPP',))

After:

- ('analyte', 'imazamox', ('RF-0247-001-PPP',))

### RD 132: Indoxacarb (sum of indoxacarb and its R enantiomer)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Indoxacarb', ('RF-0251-001-PPP',))

After:

- ('analyte', 'indoxacarb', ('RF-0251-001-PPP',))

### RD 135: Iprodione

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Iprodione', ('RF-0255-001-PPP',))

After:

- ('analyte', 'iprodione', ('RF-0255-001-PPP',))
- ('group', 'metabolites containing the 3,5-dichloroaniline moiety', ())

### RD 135: Sum of iprodione and all metabolites containing the 3,5-dichloroaniline moiety, expressed as iprodione

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'iprodione', ('RF-0255-001-PPP',))
- ('group', 'metabolites containing the 3,5-dichloroaniline moiety', ())

After:

- ('analyte', 'iprodione', ('RF-0255-001-PPP',))
- ('group', 'all metabolites containing the 3,5-dichloroaniline moiety', ())

### RD 139: Kresoxim-methyl

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'kresoxim-methyl', ('RF-0260-001-PPP',))

After:

- ('analyte', 'Kresoxim-methyl', ('RF-0260-001-PPP',))

### RD 148: Mepanipyrim

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Mepanipyrim', ('RF-0274-002-PPP',))

After:

- ('analyte', '2-anilino-4-(2-hydroxypropyl)-6-methylpyrimidine', ())
- ('analyte', 'mepanipyrim', ('RF-0274-002-PPP',))

### RD 157: Methomyl

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Methomyl', ('RF-0293-003-PPP',))

After:

- ('analyte', 'methomyl', ('RF-0293-003-PPP',))
- ('analyte', 'thiodicarb', ())

### RD 168: Oxadiargyl

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Oxadiargyl', ('RF-0317-001-PPP',))

After:

- ('analyte', 'oxadiargyl', ('RF-0317-001-PPP',))

### RD 176: Pendimethalin

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Pendimethalin', ('RF-0331-001-PPP',))

After:

- ('analyte', 'pendimethalin', ('RF-0331-001-PPP',))

### RD 185: Procymidone

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Procymidone', ('RF-0350-001-PPP',))

After:

- ('analyte', 'procymidone', ('RF-0350-001-PPP',))

### RD 185: Vinclozolin, iprodione, procymidone, sum of compounds and all metabolites containing the 3,5-dichloroaniline moiety expressed as 3,5 dichloroaniline

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Vinclozolin', ('RF-0450-003-PPP',))
- ('analyte', 'iprodione', ('RF-0255-001-PPP',))
- ('analyte', 'procymidone', ('RF-0350-001-PPP',))
- ('group', 'all metabolites containing the 3,5-dichloroaniline moiety', ())

After:

- ('analyte', 'iprodione', ('RF-0255-001-PPP',))
- ('analyte', 'procymidone', ('RF-0350-001-PPP',))
- ('analyte', 'vinclozolin', ('RF-0450-003-PPP',))
- ('group', 'compounds and all metabolites containing the 3,5-dichloroaniline moiety', ())

### RD 187: Prohexadione (prohexadione (acid) and its salts expressed as prohexadione-calcium)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Prohexadione', ('RF-0352-002-PPP',))

After:

- ('analyte', 'prohexadione', ('RF-0352-002-PPP',))

### RD 190: Propoxur

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Propoxur', ('RF-0361-001-PPP',))

After:

- ('analyte', 'propoxur', ('RF-0361-001-PPP',))

### RD 192: Sum of propyzamide and all metabolites containing the 3,5-dichlorobenzoic acid moiety, expressed as propyzamide

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'propyzamide', ('RF-0364-001-PPP',))
- ('group', 'metabolites containing the 3,5-dichlorobenzoic acid moiety', ())

After:

- ('analyte', 'propyzamide', ('RF-0364-001-PPP',))
- ('group', 'all metabolites containing the 3,5-dichlorobenzoic acid moiety', ())

### RD 194: Pymetrozine

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Pymetrozine', ('RF-0369-001-PPP',))

After:

- ('analyte', 'pymetrozine', ('RF-0369-001-PPP',))

### RD 203: Resmethrin (resmethrin including other mixtures of consituent isomers (sum of isomers))

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Resmethrin', ('RF-0385-001-PPP',))

After:

- ('analyte', 'resmethrin', ('RF-0385-001-PPP',))

### RD 214: Thiram (expressed as thiram)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Thiram', ('RF-0423-001-PPP',))

After:

- ('analyte', 'thiram', ('RF-0423-001-PPP',))

### RD 241: Benfluralin

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Benfluralin', ('RF-0039-001-PPP',))

After:

- ('analyte', 'benfluralin', ('RF-0039-001-PPP',))

### RD 249: Butralin

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Butralin', ('RF-0057-001-PPP',))

After:

- ('analyte', 'butralin', ('RF-0057-001-PPP',))

### RD 251: Carbetamide (sum of carbetamide and its S isomer)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Carbetamide', ('RF-0064-001-PPP',))

After:

- ('analyte', 'carbetamide', ('RF-0064-001-PPP',))

### RD 266: Cyproconazole

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Cyproconazole', ('RF-0113-001-PPP',))

After:

- ('analyte', 'cyproconazole', ('RF-0113-001-PPP',))

### RD 284: Dinocap (sum of dinocap isomers and their corresponding phenols expressed as dinocap) (Where only meptyldinocap or its corresponding phenol are detected but none of the other components constituting dinocap (including their corresponding phenols), the MRLs and residue definition of meptyldinocap are to be applied.)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: ['RF-00002838-PAR']; added: [].

Before:

- ('analyte', 'Dinocap', ('RF-0143-002-PPP',))
- ('analyte', 'meptyldinocap', ('RF-00002838-PAR',))
- ('analyte', 'meptyldinocap corresponding phenol', ())

After:

- ('analyte', 'dinocap', ('RF-0143-002-PPP',))
- ('analyte', 'dinocap phenol', ())

### RD 285: Dithianon

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Dithianon', ('RF-0150-001-PPP',))

After:

- ('analyte', 'dithianon', ('RF-0150-001-PPP',))

### RD 289: EPTC (ethyl dipropylthiocarbamate)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'EPTC', ('RF-0158-001-PPP',))

After:

- ('analyte', 'EPTC (ethyl dipropylthiocarbamate)', ('RF-0158-001-PPP',))

### RD 300: Fenpropidin (sum of fenpropidin and its salts, expressed as fenpropidin)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fenpropidin', ('RF-00007586-PAR',))

After:

- ('analyte', 'fenpropidin', ('RF-00007586-PAR',))

### RD 301: Fenpyroximate (metabolite M-3, expressed as fenpyroximate (F))

Previous: `model`; new: `guided_model`.
Removed PARAM codes: ['RF-0186-001-PPP']; added: ['RF-00005723-PAR'].

Before:

- ('analyte', 'fenpyroximate', ('RF-0186-001-PPP',))
- ('analyte', 'fenpyroximate metabolite M-3', ())

After:

- ('analyte', 'fenpyroximate metabolite M-3', ('RF-00005723-PAR',))

### RD 310: Fluoxastrobin (sum of fluoxastrobin, its Z-isomer and its metabolite 6-(2-chlorophenoxy)-5-fluoro-4-pyrimidinol, expressed as fluoxastrobin)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '6-(2-chlorophenoxy)-5-fluoro-4-pyrimidinol', ())
- ('analyte', 'fluoxastrobin', ('RF-0211-001-PPP',))

After:

- ('analyte', '6-(2-chlorophenoxy)-5-fluoro-4-pyrimidinol', ())
- ('analyte', 'fluoxastrobin', ('RF-0211-001-PPP',))
- ('analyte', 'fluoxastrobin Z-isomer', ())

### RD 314: Flutolanil

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flutolanil', ('RF-0219-001-PPP',))

After:

- ('analyte', 'flutolanil', ('RF-0219-001-PPP',))
- ('group', 'metabolites containing the 2-trifluoromethylbenzoic acid moiety', ())

### RD 314: Flutolanil (Flutolanil and metabolites containing the 2-trifluoromethylbenzoic acid moiety, expressed as flutolanil)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flutolanil', ('RF-0219-001-PPP',))
- ('group', 'metabolites containing the 2-trifluoromethylbenzoic acid moiety', ())

After:

- ('analyte', 'flutolanil', ('RF-0219-001-PPP',))
- ('group', 'metabolites containing the 2-trifluoromethylbenzoic acid moiety', ())

### RD 330: Mepiquat (sum of mepiquat and its salts, expressed as mepiquat chloride)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Mepiquat', ('RF-0275-001-PPP',))

After:

- ('analyte', 'mepiquat', ('RF-0275-001-PPP',))

### RD 332: Metam (see methylisothiocyanate)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: ['RF-00013459-PAR', 'RF-0118-001-PPP', 'RF-0790-001-PPP'].

Before:

- ('analyte', 'Metam', ())

After:

- ('analyte', 'Metam', ())
- ('analyte', 'methylisothiocyanate', ('RF-00013459-PAR', 'RF-0118-001-PPP', 'RF-0790-001-PPP'))

### RD 351: Phenothrin (phenothrin including other mixtures of constituent isomers (sum of isomers))

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Phenothrin', ('RF-00012805-PAR',))

After:

- ('analyte', 'phenothrin', ('RF-00012805-PAR',))

### RD 354: Phosphane and phosphide salts (sum of phosphane and phosphane generators (relevant phosphide salts), determined and expressed as phosphane)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: ['RF-00005719-PAR']; added: [].

Before:

- ('analyte', 'Phosphane and phosphide salts', ('RF-00005719-PAR',))

After:

- ('analyte', 'phosphane', ())
- ('group', 'phosphane generators (relevant phosphide salts)', ())

### RD 358: Propachlor: oxalinic derivate of propachlor, expressed as propachlor

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'propachlor', ('RF-0353-001-PPP',))

After:

- ('analyte', 'oxalinic derivate of propachlor', ('RF-0353-001-PPP',))

### RD 359: Propamocarb (Sum of propamocarb and its salts, expressed as propamocarb)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Propamocarb', ('RF-0354-001-PPP',))

After:

- ('analyte', 'propamocarb', ('RF-0354-001-PPP',))

### RD 375: Spiromesifen

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Spiromesifen', ('RF-0395-001-PPP',))

After:

- ('analyte', 'spiromesifen', ('RF-0395-001-PPP',))

### RD 380: Tebufenozide

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Tebufenozide', ('RF-0404-001-PPP',))

After:

- ('analyte', 'tebufenozide', ('RF-0404-001-PPP',))

### RD 384: Terbufos

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Terbufos', ('RF-0412-002-PPP',))

After:

- ('analyte', 'terbufos', ('RF-0412-002-PPP',))
- ('analyte', 'terbufos sulfone', ())
- ('analyte', 'terbufos sulfoxide', ())

### RD 393: Triclopyr

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Triclopyr', ('RF-0436-001-PPP',))

After:

- ('analyte', '3,5,6-trichloro-2-pyridinol', ())
- ('analyte', 'triclopyr', ('RF-0436-001-PPP',))

### RD 394: Tricyclazole

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Tricyclazole', ('RF-0437-001-PPP',))

After:

- ('analyte', 'tricyclazole', ('RF-0437-001-PPP',))

### RD 398: Trinexapac (sum of trinexapac (acid) and its salts, expressed as trinexapac)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Trinexapac', ('RF-0446-001-PPP',))

After:

- ('analyte', 'trinexapac (acid)', ('RF-0446-001-PPP',))

### RD 399: 1,4-Diaminobutane  (aka Putrescine)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '1,4-Diaminobutane', ())
- ('analyte', 'Putrescine', ())

After:

- ('analyte', '1,4-Diaminobutane', ())

### RD 412: Fatty acids / Lauric acid

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Lauric acid', ())
- ('group', 'Fatty acids', ())

After:

- ('analyte', 'Lauric acid', ())

### RD 413: Fatty acids C7-C20

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fatty acids C10', ())
- ('analyte', 'Fatty acids C11', ())
- ('analyte', 'Fatty acids C12', ())
- ('analyte', 'Fatty acids C13', ())
- ('analyte', 'Fatty acids C14', ())
- ('analyte', 'Fatty acids C15', ())
- ('analyte', 'Fatty acids C16', ())
- ('analyte', 'Fatty acids C17', ())
- ('analyte', 'Fatty acids C18', ())
- ('analyte', 'Fatty acids C19', ())
- ('analyte', 'Fatty acids C20', ())
- ('analyte', 'Fatty acids C7', ())
- ('analyte', 'Fatty acids C8', ())
- ('analyte', 'Fatty acids C9', ())

After:

- ('analyte', 'Fatty acids C7-C20', ())

### RD 418: Fatty acids: Oleic acid incl ethyloleate

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Oleic acid', ())
- ('analyte', 'ethyloleate', ())

After:

- ('analyte', 'ethyloleate', ())
- ('analyte', 'oleic acid', ())

### RD 422: Ferric sulphate (Iron (III) sulphate)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Ferric sulphate', ())

After:

- ('analyte', 'Ferric sulphate (Iron (III) sulphate)', ())

### RD 428: Kieselguhr  (aka diatomaceous earth)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Kieselguhr (diatomaceous earth)', ())

After:

- ('analyte', 'Kieselguhr', ())

### RD 438: Plant oils / Spearmint oil

Previous: `model`; new: `rules`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Spearmint oil', ())

After:

- ('analyte', 'Plant oils / Spearmint oil', ())

### RD 440: Potassium Iodide

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Potassium Iodide', ())

After:

- ('analyte', 'Potassium iodide', ())

### RD 468: Propham

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Propham', ('RF-0867-001-PPP',))

After:

- ('analyte', 'propham', ('RF-0867-001-PPP',))

### RD 776: Cyflufenamid (sum of cyflufenamid (Z-isomer) and its E-isomer, expressed as cyflufenamid)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: ['RF-0107-001-PPP']; added: ['RF-00007590-PAR'].

Before:

- ('analyte', 'cyflufenamid', ('RF-0107-001-PPP',))

After:

- ('analyte', 'cyflufenamid (Z-isomer)', ('RF-00007590-PAR',))
- ('analyte', 'cyflufenamid E-isomer', ())

### RD 776: sum of cyflufenamid (Z-isomer), its E-isomer and metabolite 149-F1, expressed as cyflufenamid

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: ['RF-00007590-PAR'].

Before:

- ('analyte', '149-F1', ('RF-00012292-PAR',))
- ('analyte', 'cyflufenamid E-isomer', ())
- ('analyte', 'cyflufenamid Z-isomer', ())

After:

- ('analyte', '149-F1', ('RF-00012292-PAR',))
- ('analyte', 'cyflufenamid (Z-isomer)', ('RF-00007590-PAR',))
- ('analyte', 'cyflufenamid E-isomer', ())

### RD 779: Flubendiamide

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flubendiamide', ('RF-0199-001-PPP',))

After:

- ('analyte', 'flubendiamide', ('RF-0199-001-PPP',))

### RD 784: Flurprimidole

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flurprimidole', ('RF-0216-001-PPP',))

After:

- ('analyte', 'Flurprimidol', ('RF-0216-001-PPP',))

### RD 790: Mandipropamid (any ratio of constituent isomers)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Mandipropamid', ('RF-00012047-PAR', 'RF-0268-001-PPP'))

After:

- ('analyte', 'mandipropamid', ('RF-00012047-PAR', 'RF-0268-001-PPP'))

### RD 802: Pyrasulfotole

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Pyrasulfotole', ('RF-0372-001-PPP',))

After:

- ('analyte', 'pyrasulfotole', ('RF-0372-001-PPP',))

### RD 808: Tembotrione (Sum of parent tembotrione (AE 0172747) and its metabolite M5 (4,6-dihydroxy tembotrione), expressed as tembotrione)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '4,6-dihydroxy tembotrione (M5)', ('RF-00002608-PAR',))
- ('analyte', 'tembotrione (AE 0172747)', ('RF-0409-001-PPP',))

After:

- ('analyte', 'M5 (4,6-dihydroxy tembotrione)', ('RF-00002608-PAR',))
- ('analyte', 'tembotrione (AE 0172747)', ('RF-0409-001-PPP',))

### RD 810: Topramezone (BAS 670H)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Topramezone', ('RF-0426-001-PPP',))

After:

- ('analyte', 'Topramezone (BAS 670H)', ('RF-0426-001-PPP',))

### RD 811: Tralkoxydim (sum of the constituent isomers of tralkoxydim)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Tralkoxydim', ('RF-0427-001-PPP',))

After:

- ('analyte', 'tralkoxydim', ('RF-0427-001-PPP',))

### RD 2080: Amisulbrom

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Amisulbrom', ('RF-0470-001-PPP',))

After:

- ('analyte', 'amisulbrom', ('RF-0470-001-PPP',))

### RD 2268: Fluxapyroxad

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fluxapyroxad', ('RF-00000024-PAR',))

After:

- ('analyte', 'fluxapyroxad', ('RF-00000024-PAR',))

### RD 2309: Aureobasidium pullulans strains DSM 14940 and DSM 14941

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Aureobasidium pullulans strain DSM 14940', ())
- ('analyte', 'Aureobasidium pullulans strain DSM 14941', ())

After:

- ('analyte', 'Aureobasidium pullulans strains DSM 14940 and DSM 14941', ())

### RD 2321: Pyriofenone

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Pyriofenone', ('RF-00003031-PAR',))

After:

- ('analyte', 'pyriofenone', ('RF-00003031-PAR',))

### RD 2332: Didecyldimethylammonium chloride (mixture of alkyl-quaternary ammonium salts with alkyl chain lengths of C8, C10 and C12)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Didecyldimethylammonium chloride, alkyl-quaternary ammonium salt with alkyl chain length of C10', ('RF-00007627-PAR',))
- ('analyte', 'Didecyldimethylammonium chloride, alkyl-quaternary ammonium salt with alkyl chain length of C12', ('RF-00007489-PAR',))
- ('analyte', 'Didecyldimethylammonium chloride, alkyl-quaternary ammonium salt with alkyl chain length of C8', ('RF-00007495-PAR',))

After:

- ('analyte', 'alkyl-quaternary ammonium salts with alkyl chain length of C10', ('RF-00007627-PAR',))
- ('analyte', 'alkyl-quaternary ammonium salts with alkyl chain length of C12', ('RF-00007489-PAR',))
- ('analyte', 'alkyl-quaternary ammonium salts with alkyl chain length of C8', ('RF-00007495-PAR',))

### RD 2333: Benzalkonium chloride (mixture of alkylbenzyldimethylammonium chlorides with alkyl chain lengths of C8, C10, C12, C14, C16 and C18)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'alkylbenzyldimethylammonium chloride C10', ('RF-1078-003-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride C12', ('RF-1078-004-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride C14', ('RF-1078-005-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride C16', ('RF-1078-006-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride C18', ('RF-1078-007-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride C8', ('RF-00003376-PAR',))

After:

- ('analyte', 'alkylbenzyldimethylammonium chloride with alkyl chain length C10', ('RF-1078-003-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride with alkyl chain length C12', ('RF-1078-004-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride with alkyl chain length C14', ('RF-1078-005-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride with alkyl chain length C16', ('RF-1078-006-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride with alkyl chain length C18', ('RF-1078-007-PPP',))
- ('analyte', 'alkylbenzyldimethylammonium chloride with alkyl chain length C8', ('RF-00003376-PAR',))

### RD 2344: Bone oil

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'bone oil', ('RF-00011518-PAR',))

After:

- ('analyte', 'Bone oil', ('RF-00011518-PAR',))

### RD 2347: Paraffin oil (CAS 64742-54-7)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Paraffin oil (CAS 64742-54-7)', ('RF-00014619-PAR',))

After:

- ('analyte', 'Paraffin oil', ('RF-00014619-PAR',))

### RD 2348: Petroleum oils (CAS 92062-35-6)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Petroleum oils (CAS 92062-35-6)', ('RF-00014630-PAR',))

After:

- ('analyte', 'Petroleum oils', ('RF-00014630-PAR',))

### RD 2380: Flumetralin

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Flumetralin', ('RF-0706-001-PPP',))

After:

- ('analyte', 'flumetralin', ('RF-0706-001-PPP',))

### RD 2409: Paraffin oil (CAS 64742-46-7)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Paraffin oil (CAS 64742-46-7)', ('RF-00014619-PAR',))

After:

- ('analyte', 'Paraffin oil', ('RF-00014619-PAR',))

### RD 2412: Paraffin oil (CAS 97862-82-3)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Paraffin oil (CAS 97862-82-3)', ('RF-00014619-PAR',))

After:

- ('analyte', 'Paraffin oil', ('RF-00014619-PAR',))

### RD 2417: Sodium 5-nitroguaiacolate, sodium o-nitrophenolate and sodium p-nitrophenolate (Sum of sodium 5-nitroguaiacolate, sodium o-nitrophenolate and sodium p-nitrophenolate, expressed as sodium 5-nitroguaiacolate)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Sodium 5-nitroguaiacolate', ('RF-00005776-PAR',))
- ('analyte', 'Sodium o-nitrophenolate', ('RF-00005777-PAR',))
- ('analyte', 'Sodium p-nitrophenolate', ('RF-00005778-PAR',))

After:

- ('analyte', 'sodium 5-nitroguaiacolate', ('RF-00005776-PAR',))
- ('analyte', 'sodium o-nitrophenolate', ('RF-00005777-PAR',))
- ('analyte', 'sodium p-nitrophenolate', ('RF-00005778-PAR',))

### RD 2419: Thiodicarb

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Thiodicarb', ('RF-0293-002-PPP',))

After:

- ('analyte', 'methomyl', ())
- ('analyte', 'thiodicarb', ('RF-0293-002-PPP',))

### RD 2428: Cerevisane

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Cerevisane', ())

After:

- ('analyte', 'cerevisane', ())

### RD 2476: Oxathiapiprolin

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Oxathiapiprolin', ('RF-00008949-PAR',))

After:

- ('analyte', 'oxathiapiprolin', ('RF-00008949-PAR',))

### RD 2494: Urtica spp.

Previous: `model`; new: `rules`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Urtica spp.', ())

After:

- ('analyte', 'Urtica spp', ())

### RD 2513: Fenpicoxamid

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Fenpicoxamid', ('RF-00010217-PAR',))

After:

- ('analyte', 'fenpicoxamid', ('RF-00010217-PAR',))

### RD 2516: Talc E553B

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Talc', ('RF-00000327-ADD',))

After:

- ('analyte', 'Talc E553B', ('RF-00000327-ADD',))

### RD 2536: Bicyclopyrone (sum of bicyclopyrone and its structurally related metabolites determined as the sum of the common moieties 2-(2- methoxyethoxymethyl)-6-(trifluoromethyl) pyridine-3-carboxylic acid (SYN503780) and (2-(2-hydroxyethoxymethyl)-6- (trifluoromethyl)pyridine-3-carboxylic acid (CSCD686480), expressed as bicyclopyrone)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '2-(2-hydroxyethoxymethyl)-6-(trifluoromethyl)pyridine-3-carboxylic acid (CSCD686480)', ('RF-00011517-PAR',))
- ('analyte', '2-(2-methoxyethoxymethyl)-6-(trifluoromethyl)pyridine-3-carboxylic acid (SYN503780)', ('RF-00011516-PAR',))
- ('analyte', 'bicyclopyrone', ('RF-00011514-PAR',))

After:

- ('analyte', '2-(2-hydroxyethoxymethyl)-6-(trifluoromethyl)pyridine-3-carboxylic acid (CSCD686480)', ('RF-00011517-PAR',))
- ('analyte', '2-(2-methoxyethoxymethyl)-6-(trifluoromethyl)pyridine-3-carboxylic acid (SYN503780)', ('RF-00011516-PAR',))
- ('analyte', 'bicyclopyrone', ('RF-00011514-PAR',))
- ('group', 'structurally related metabolites of bicyclopyrone', ())

### RD 2543: Clonostachys rosea strain J1446 (formerly Gliocladium catenulatum strain J1446)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Clonostachys rosea strain J1446 (formerly Gliocladium catenulatum strain J1446)', ())

After:

- ('analyte', 'Clonostachys rosea strain J1446', ())

### RD 2690: Tefluthrin (tefluthrin including other mixtures of constituent isomers (sum of isomers))

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Tefluthrin', ('RF-0408-001-PPP',))

After:

- ('analyte', 'tefluthrin', ('RF-0408-001-PPP',))

### RD 2770: Aqueous extract from the germinated seeds of sweet Lupinus albus

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'aqueous extract from the germinated seeds of sweet Lupinus albus', ())

After:

- ('analyte', 'Aqueous extract from the germinated seeds of sweet Lupinus albus', ())

### RD 2790: Quinmerac (sum of quinmerac and its metabolites BH 518-2 and BH 518-4 expressed as quinmerac)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'BH 518-2', ('RF-00007283-PAR',))
- ('analyte', 'BH 518-4', ('RF-00007284-PAR',))
- ('analyte', 'Quinmerac', ('RF-0381-001-PPP',))

After:

- ('analyte', 'BH 518-2', ('RF-00007283-PAR',))
- ('analyte', 'BH 518-4', ('RF-00007284-PAR',))
- ('analyte', 'quinmerac', ('RF-0381-001-PPP',))

### RD 3030: 1-methyl-3-(trifluoromethyl)-1H-pyrazole-4-carboxamide (PAM)

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '1-methyl-3-(trifluoromethyl)-1H-pyrazole-4-carboxamide', ('RF-00009238-PAR',))

After:

- ('analyte', '1-methyl-3-(trifluoromethyl)-1H-pyrazole-4-carboxamide (PAM)', ('RF-00009238-PAR',))

### RD 3050: Cycloxydim including degradation and reaction products which can be determined as 3-(3-thianyl)glutaric acid S-dioxide (BH 517-TGSO2) and/or 3-hydroxy-3-(3-thianyl)glutaric acid S-dioxide (BH 517-5-OH-TGSO2) or derivatives thereof, calculated in total as cycloxydim

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', '3-(3-thianyl)glutaric acid S-dioxide (BH 517-TGSO2)', ('RF-00006227-PAR',))
- ('analyte', '3-hydroxy-3-(3-thianyl)glutaric acid S-dioxide (BH 517-5-OH-TGSO2)', ('RF-00006240-PAR',))
- ('analyte', 'Cycloxydim', ('RF-0106-002-PPP',))

After:

- ('analyte', '3-(3-thianyl)glutaric acid S-dioxide (BH 517-TGSO2)', ('RF-00006227-PAR',))
- ('analyte', '3-hydroxy-3-(3-thianyl)glutaric acid S-dioxide (BH 517-5-OH-TGSO2)', ('RF-00006240-PAR',))
- ('analyte', 'cycloxydim', ('RF-0106-002-PPP',))

### RD 3231: Repellants: Sheep fat

Previous: `model`; new: `rules`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Repellants', ())

After:

- ('analyte', 'Sheep fat', ())

### RD 3370: Sum of metalaxyl (sum of enantiomers) and metabolites (free + conjugated) M3 (N- (2,6-dimethylphenyl)-N-(hydroxyacetyl)alanine methyl ester) and M8 (N-(2-hydroxymethyl-6- methylphenyl)-N-(methoxyacetyl)alanine methyl ester (sum of enantiomers), expressed as metalaxyl

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'M3 (N- (2,6-dimethylphenyl)-N-(hydroxyacetyl)alanine methyl ester)', ('RF-00015696-PAR',))
- ('analyte', 'M8 (N-(2-hydroxymethyl-6- methylphenyl)-N-(methoxyacetyl)alanine methyl ester)', ('RF-00015697-PAR',))
- ('analyte', 'metalaxyl', ('RF-0281-002-PPP',))

After:

- ('analyte', 'M3 (N-(2,6-dimethylphenyl)-N-(hydroxyacetyl)alanine methyl ester)', ('RF-00015696-PAR',))
- ('analyte', 'M8 (N-(2-hydroxymethyl-6-methylphenyl)-N-(methoxyacetyl)alanine methyl ester)', ('RF-00015697-PAR',))
- ('analyte', 'metalaxyl', ('RF-0281-002-PPP',))

### RD 3430: Phosphonic acid and its salts expressed as phosphonic acid

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Phosphonic acid', ('RF-00004675-PAR',))

After:

- ('analyte', 'phosphonic acid', ('RF-00004675-PAR',))

### RD 3850: Plant oils / Citronella oil

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Citronella oil', ())

After:

- ('analyte', 'Citronella oil', ())
- ('group', 'Plant oils', ())

### RD 3890: Triflusulfuron (6-(2,2,2-trifluoroethoxy)-1,3,5-triazine-2,4-diamine (IN-M7222))

Previous: `model`; new: `guided_model`.
Removed PARAM codes: []; added: [].

Before:

- ('analyte', 'Triflusulfuron (6-(2,2,2-trifluoroethoxy)-1,3,5-triazine-2,4-diamine (IN-M7222))', ('RF-00005716-PAR',))

After:

- ('analyte', '6-(2,2,2-trifluoroethoxy)-1,3,5-triazine-2,4-diamine (IN-M7222)', ('RF-00005716-PAR',))

