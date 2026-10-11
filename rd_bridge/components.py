"""What a residue definition consists of, and whether an analysis covered all of it.

A definition such as "sum of acetamiprid and N-desmethyl-acetamiprid (IM-2-1), expressed as
acetamiprid" has one summed PARAM code and one PARAM code per part. This splits a definition
into parts and links each analyte to PARAM:

- analyte: a substance that can be measured (acetamiprid, IM-2-1, methiocarb sulfoxide);
- group: parts that cannot be enumerated ("all metabolites containing the ... moiety");
- qualifier: "its salts", "esters", "conjugates", E/Z/R/S isomers and enantiomers; kept as
  notes, never required for completeness.

Each analyte is looked up first in the PARAM family of the substance the residue is about
(PARAM's main hierarchy places a substance's metabolites under it), then across all pesticide
terms, where short codes count only if a single term carries them. `completeness` answers
whether a set of analysed PARAM codes covers the definition.
"""
import collections
import json
import re

from rd_bridge import compounds

NOTE = (r"both free and conjugated|free and conjugated|free \+ conjugated|free|conjugated|sum of isomers|"
        r"sum of enantiomers|"
        r"[EZRS]-isomer|any ratio of constituent isomers[^)]*|including [^)]*")
NOTES = re.compile(rf"\s*\(({NOTE})\)", re.I)
STEREO = r"(?:[EZRS]|RS|R,S|S,R|cis|trans)"
QUALIFIER = re.compile(
    rf"^(?:its |their |the )?(?:other mixtures of )?(?:constituent |consituent |corresponding )?"
    rf"(?:{STEREO}[- ]?(?:and {STEREO}[- ]?)?)?(?:salts?|esters?|conjugates?|isomers?|enantiomers?|"
    rf"diastereo(?:iso)?mers?|diasteroisomers?)$"
    rf"|^(?:other mixtures of )?(?:constituent|consituent)$|^any ratio of constituent isomers.*$"
    rf"|^(?:both )?(?:free|conjugated|free and conjugated)$|^[EZRS]-?$|^[a-z]{{1,2}}[´′']?(?:,[a-z]{{1,2}}[´′']?)?$",
    re.I)
# a named conjugate is a substance of its own (PARAM codes "5-Hydroxythiabendazole O-sulfate conjugate")
NAMED_CONJUGATE = re.compile(r"^(?:its |their )?(?:O-)?(sulfate|sulphate|phosphate|glucoside|glucuronide)"
                             r" conjugates?$", re.I)
POSITIONAL = re.compile(r"^(alpha|beta|gamma|delta|cis|trans|E|Z|[mop],[mop][´′']?)-?\s?(?:isomers?)?$", re.I)
GROUP = re.compile(r"\b(?:metabolites|compounds|products|derivatives)\b.*\b(?:containing|oxidi[sz]ed|"
                   r"hydroly[sz]ed|determined|moiety)\b|degradation|corresponding phenols|^components$|"
                   r"^compounds$|hydrolysable conjugates|derivatives thereof", re.I)
DERIVATIVE = re.compile(r"^(?:sulf|sulph)(?:oxides?|ones?)$|^oxon$|^oxide$|^ox[iy]gen analogue$", re.I)
SUMMED_TOP = re.compile(r"\bsum of\b|\bincluding\b", re.I)
# stereo descriptors are single tokens ("R-", "S,R", "cis-"), each optionally followed by "and"
NAMED_ISOMERS = re.compile(r"\b(?:E|Z|R|S|cis|trans)-(?: |$|and\b)", re.I)
STEREO_NOTE = re.compile(
    r"(?:sum of )?(?:the )?(?:(?:[A-Z]{1,2}(?:,[A-Z]{1,2})?|cis|trans)(?:- ?| )(?:and )?)*(?:constituent )?"
    r"(?:isomers|enantiomers|diastereo\w*|diasteroisomers)(?: at any ratio)?", re.I)
MOIETY_LEAD = re.compile(r"^.*?\bdetermined as (?:the )?sum of (?:the )?(?:common )?moiet(?:y|ies)\s+", re.I)
CODE_PREFIX = re.compile(r"^([A-Z]{2,}[\w-]*\s*\d[\w-]*)\s+(.+)$")  # "RPA 202248 diketonitrile-metabolite"
GENERIC_CODE = re.compile(r"^m\d{1,3}[a-z]?$")  # M4, M23: metabolite numbers repeat across substances
PREFIX = re.compile(r"^[\d,]+-(?:hydroxy|keto|oxo|methoxy|hydroxymethyl|desmethyl|desethyl)$", re.I)
SUM_WORDS = re.compile(r"\bsum\b|\bincludes?\b|\bincluding\b|\bplus\b|expressed as|calculated", re.I)
SPLIT = re.compile(r",\s+(?:and\s+)?|\s+and/or\s+|\s+and\s+|\s+plus\s+|\s+\+\s+|\s+including\s+|\s+includes\s+", re.I)
LEAD = re.compile(r"^(?:the |sum of |the sum of |sum (?=\w)|(?:all )?(?:the )?constituent isomers of |parent |its metabolites? |their metabolites? |metabolites? |"
                  r"its hydrolysis products? |hydrolysis products? |[\w-]+ metabolites? (?=\S)|their |its |all |"
                  r"(?:two|three|four|five) indicator compounds )+", re.I)
TRAIL = re.compile(r"\s+(?:combined|free|isomers)$|,?\s*(?:determined|calculated)(?:\s+and)?$", re.I)


def _clean(text: str) -> str:
    text = compounds.MARKERS.sub("", text.strip().rstrip("."))
    text = re.sub(r"\s*\(Where only.*$", "", text, flags=re.S)
    text = text.replace("–", "-").replace("\xad", "")
    text = re.sub(r"\b([mop])\s*,\s+([mop][´′']?)", r"\1,\2", text)  # "p, p´" -> "p,p´"
    text = re.sub(r"(?<=\w)\s*-\s+(?!and\b|or\b)(?=[\w(])|(?<=\w)\s+-(?=\w)", "-", text)
    # "M23 free and conjugated" -> one part with a note, not two parts
    return re.sub(r"(?<!\()\b((?:both )?free and conjugated)\b(?!\))", r"(\1)", text, flags=re.I)


def _summed(name: str) -> bool:
    """A summed PARAM term: its parenthesis (nested or not) or its text defines a sum."""
    _, body = compounds._head_and_body(name)
    return bool(SUMMED_TOP.search(name) or (body != name and re.search(r"\b(?:sum|expressed)\b", body, re.I)))


def _balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if depth < 0:
            return False
    return depth == 0


def _repair_parentheses(text: str) -> tuple:
    """Drop the one stray bracket that leaves the shortest head (the EU text sometimes opens a
    parenthesis it never closes). Returns (text, repaired?)."""
    if _balanced(text):
        return text, False
    stray = "(" if text.count("(") > text.count(")") else ")"
    candidates = [text[:i] + text[i + 1:] for i, ch in enumerate(text) if ch == stray]
    candidates = [c for c in candidates if _balanced(c)]
    if not candidates:
        return text, False
    return min(candidates, key=lambda c: len(compounds._head_and_body(c)[0] or c)), True


def parts(definition: str) -> tuple:
    """Return (anchor name, [part]); a part is {text, name, role, notes[, expanded_from]}."""
    text, repaired = _repair_parentheses(_clean(definition))
    text = re.sub(r"^[^:()]{2,60}:\s*(?=\S)", "", text)  # "Triflumizole: Triflumizole and ..."
    stereo = []
    head, body = compounds._head_and_body(text)
    while (head and STEREO_NOTE.fullmatch(body.strip())
           and not (NAMED_ISOMERS.search(body) and not re.search(r"[(,]|\band\b|\bsum\b", head, re.I))):
        # "Mevinphos (sum of E- and Z-isomers)" names its parts; only a note after a clause that already does
        # "... expressed as haloxyfop (sum of the R- and S- isomers at any ratio)": a note, not the body
        stereo.append(body.strip().lower())
        text = head
        head, body = compounds._head_and_body(text)
    if head and not SUM_WORDS.search(body) and not re.search(r"\band\b|,", body):
        head, body = None, text
    if head and re.match(r"^includ(?:es|ing)\s+", body, re.I):
        body = f"{head} including {re.sub(r'^includ(?:es|ing)\s+', '', body, flags=re.I)}"  # "X (includes Y)"
    if head and re.match(r"^(?:sum of (?:isomers|constituent isomers|diasteroisomers)|sum of|mixture of .*)$",
                         body, re.I):
        body = head  # "Bifenthrin (sum of isomers)", "X chloride (mixture of ...)": one analyte
    expressed = None
    m = compounds.EXPRESSED.match(body)
    if m:
        expressed = m.group(2).strip() or None
        body = m.group(1)
    body = TRAIL.sub("", body.strip())
    if head:
        m = re.match(rf"^{re.escape(head)}\s*,\s*sum of\s+(.*)$", body, re.I)
        if m:
            body = m.group(1)  # "Spinosad (spinosad, sum of spinosyn A and spinosyn D)"
    if expressed and compounds.canon(expressed) in compounds.PARENT_WORDS:
        expressed = None
    anchor = expressed or head
    is_sum = bool(SUM_WORDS.search(definition)) or (bool(re.search(r"\s+and\s+", body)) and "strain" not in body)
    if is_sum:
        marked = re.sub(r"\s+includ(?:ing|es)\s+", " including \u00a7", compounds.SUM_TAIL.sub("", body), flags=re.I)
        raw = compounds._top_level(marked, SPLIT)
    else:
        raw = [body]

    out = []
    for piece in raw:
        included = piece.startswith("\u00a7")  # "X including Y": Y is part of X
        piece = piece.replace("\u00a7", "")  # the marker may also sit inside a parenthesis
        notes = [n.lower() for n in NOTES.findall(piece)]
        promoted = [i for n in NOTES.findall(piece) for i in _inclusions(n)]  # "dichlorprop (including dichlorprop-P)"
        if re.search(r"constituent isomers of\b", piece, re.I):
            notes = notes + ["constituent isomers"]
        # "sulfone metabolite (MB46136)": the sulfone of the parent, not an anonymous metabolite
        shaped = re.sub(r"^(?:its |the )?((?:sulf|sulph)(?:oxide|one)|oxon) metabolite\b", r"\1", piece.strip(), flags=re.I)
        name = TRAIL.sub("", LEAD.sub("", NOTES.sub("", shaped).strip())).strip()
        moiety = MOIETY_LEAD.match(name)
        if moiety:  # "... determined as the sum of the common moieties X": X is measured
            name, notes = name[moiety.end():].strip(), notes + ["common moiety"]
        if re.search(r"\s+conjugates?$", name, re.I) and not QUALIFIER.match(name) \
                and not NAMED_CONJUGATE.match(piece.strip()):
            name, notes = re.sub(r"\s+conjugates?$", "", name, flags=re.I), notes + ["conjugates"]
        entry = {"text": piece.strip(), "name": name, "notes": notes}
        if included:
            entry["included"] = True
        if re.match(r"their\s", piece.strip(), re.I):
            entry["plural"] = True  # "their sulfones": of every substance named before
        bare = re.sub(r"\s*\([^()]*\)$", "", name)  # "RS enantiomer (KIF 230-S-D)"
        if NAMED_CONJUGATE.match(piece.strip()):
            entry.update(role="analyte", name=NAMED_CONJUGATE.match(piece.strip()).group(0))  # expanded below
        elif POSITIONAL.match(name) and not re.match(r"its [EZ]-", piece.strip()):  # "its E-isomer": a note
            entry["role"] = "analyte"  # alpha-/beta-endosulfan, cis-/trans-chlordane: expanded below
        elif not name or QUALIFIER.match(name) or (bare != name and QUALIFIER.match(bare)):
            entry.update(role="qualifier", name=None)
        elif not moiety and (GROUP.search(piece) or GROUP.search(name)):
            entry.update(role="group", name=re.sub(r"^(?:the |sum of |its |their |all )+", "", piece.strip(), flags=re.I))
        else:
            entry["role"] = "analyte"
        out.append(entry)
        for name_ in promoted:
            out.append({"text": name_, "name": name_, "role": "analyte", "notes": [f"included in {piece.strip()}"],
                        "included": entry["role"] == "analyte"})

    anchor = anchor or next((p["name"] for p in out if p["role"] == "analyte"), None)
    out = _expand(out, anchor)
    analytes = [p for p in out if p["role"] == "analyte"]
    if head and (not analytes or (out[0]["role"] == "qualifier" and "including" in body.lower())):
        # "Fenvalerate (any ratio of constituent isomers ... including esfenvalerate)"
        if not any(compounds.canon(p["name"]) == compounds.canon(head) for p in analytes):
            out.insert(0, {"text": head, "name": head, "role": "analyte", "notes": []})
    if not any(p["role"] in ("analyte", "group") for p in out):
        out.insert(0, {"text": text, "name": anchor or text, "role": "analyte", "notes": []})
    if stereo:
        first = next(p for p in out if p["role"] in ("analyte", "group"))
        first["notes"] = first["notes"] + stereo
    if repaired:
        out[0]["notes"] = out[0]["notes"] + ["unbalanced parenthesis in the source text repaired"]
    return anchor, out


def _inclusions(note: str) -> list:
    """Named substances in an "including ..." note; not origins ("any carbofuran generated from ...")
    or generic words."""
    m = re.match(r"^(?:any ratio of constituent isomers\s+)?including\s+(.+)$", note, re.I)
    if not m or re.match(r"any\b", m.group(1), re.I) or re.search(
            r"generated|derived|resulting|salts|esters|conjugates|isomers|products", m.group(1), re.I):
        return []
    return [x.strip() for x in re.split(r",\s*|\s+and\s+|\s+or\s+", m.group(1)) if x.strip()]


def _expand(out: list, anchor) -> list:
    """Shorthand: 'methiocarb sulfoxide and sulfone', 'Parlar No 26, 50 and 62', '6-hydroxy',
    'alpha- and beta-isomers' (of the anchor), 'phorate, its oxygen analogue and their sulfones'
    (the sulfones of both)."""
    previous, bases, plural, result = None, [], False, []
    for p in out:
        if p["role"] != "analyte":
            result.append(p)
            continue
        name = p["name"]
        plural = (p.pop("plural", False) or plural) and bool(DERIVATIVE.match(name))
        if plural and len(bases) > 1:
            for base in bases:
                result.append({**p, "expanded_from": name, "name": f"{base} {name}"})
            previous = f"{bases[-1]} {name}"
            continue
        conjugate = NAMED_CONJUGATE.match(name)
        if conjugate and (previous or anchor):
            p.update(expanded_from=name, name=f"{previous or anchor} {conjugate.group(1).lower()} conjugate")
        elif DERIVATIVE.match(re.sub(r"\s*\([^()]*\)$", "", name)) and (previous or anchor):
            base = previous if previous and DERIVATIVE.match(previous.split()[-1]) else None
            full = f"{' '.join(base.split()[:-1])} {name}" if base else f"{anchor or previous} {name}"
            p.update(expanded_from=name, name=full)
        elif re.fullmatch(r"\d+", name) and previous and re.search(r"\d+$", previous):
            p.update(expanded_from=name, name=re.sub(r"\d+$", name, previous))
        elif (PREFIX.match(name) or POSITIONAL.match(name)) and anchor:
            prefix = POSITIONAL.match(name).group(1) if POSITIONAL.match(name) else name
            p.update(expanded_from=name, name=f"{prefix}-{anchor}")
        if not re.search(r"(?i)\bsulf|\bsulph", p["name"]):
            bases.append(p["name"])  # substances a later "their ..." can refer to
        previous = p["name"]
        result.append(p)
    return result


def _variants(name: str) -> set:
    """Spellings of one name: inverted PARAM style ('DDT, p,p-'), OH/hydroxy, word order."""
    name = re.sub(r"\b([mop])\s*,\s+([mop][´′']?)", r"\1,\2", name)  # PARAM "Dicofol p, p'"
    out = {name}
    m = re.match(r"^(.*?),\s*([^,]+-)$", name)
    if m:
        out.add(f"{m.group(2)}{m.group(1)}")
    out |= {re.sub(r"(?i)^(.+?) isomer of (.+)$", r"\2, \1 isomer", v) for v in out}  # = "B1a, delta-8,9 isomer"
    for v in list(out):  # "E-mevinphos" = PARAM "Mevinphos E-isomer", "Metaflumizone (Z-isomer)"
        m = re.fullmatch(r"([EZ])-(.+)", v)
        if m:
            out |= {f"{m.group(2)} {m.group(1)}-isomer", f"{m.group(2)} ({m.group(1)}-isomer)"}
    out |= {re.sub(r"\bOH\b", "hydroxy", v) for v in out}
    out |= {re.sub(r"\bTDE\b", "DDD", v) for v in out}
    out |= {re.sub(r"(?i)\bmilbemycin (A[34])\b", r"milbemectin \1", v) for v in out}  # PARAM "Milbemectin A3"
    # German PARAM spellings, plurals, and the oxygen analogue ("Phorate-O-analogue", "-Oxon")
    out |= {re.sub(r"(?i)\bsulf(oxid|on)\b", r"sulf\1e", v) for v in out}
    out |= {re.sub(r"(?i)\b(sulf(?:oxide|one))s\b", r"\1", v) for v in out}
    # "Phosphate conjugate of X" = "X phosphate conjugate"; "O-sulfate" = "sulfate"
    out |= {re.sub(r"(?i)^(\w+) conjugate of (.+)$", r"\2 \1 conjugate", v) for v in out}
    out |= {re.sub(r"(?i)\bO-(sulf|sulph)", r"\1", v) for v in out}
    for v in list(out):
        if re.search(r"(?i)ox[iy]gen analogue", v):
            out |= {re.sub(r"(?i)\s*ox[iy]gen analogue", "-O-analogue", v),
                    re.sub(r"(?i)\s*ox[iy]gen analogue", "-oxon", v)}
    return out


def _keys(names) -> set:
    keys = set()
    for n in names:
        for v in _variants(n):
            if compounds.canon(v):
                keys.add(compounds.canon(v))
                tokens = sorted(compounds.canon(t) for t in re.split(r"[\s\-]+", v) if compounds.canon(t))
                if len(tokens) > 1:
                    keys.add("|".join(tokens))  # word-order free: desethyl-terbuthylazine
    return keys


def _code_like(text: str) -> bool:
    return bool(re.search(r"\d", text) or re.fullmatch(r"[A-Z][A-Z\-]{2,}", text.strip()))


def _names(name: str) -> tuple:
    """(full-name forms, trailing-parenthesis alias or None) for a term or part name."""
    head, body = compounds._head_and_body(name)
    forms = [name]
    if head:
        forms.append(head)
    m = compounds.EXPRESSED.match(name)
    if m and m.group(1).strip():
        forms.append(m.group(1).strip())  # "Spirotetramat-enol expressed as spirotetramat"
    forms += [f2 for f2 in (NOTES.sub("", f).strip(" ,") for f in forms) if f2 and f2 not in forms]  # "M4 (free and conjugated)"
    return forms, (body if head else None)


class ComponentIndex:
    def __init__(self, data: dict):
        self.terms = data["terms"]
        self.version = data.get("source", {})
        groups = {t.get("pest_parent") for t in self.terms.values()}
        self.children = collections.defaultdict(list)
        self.strong, self.weak, self.named = {}, {}, {}
        self.by_strong = collections.defaultdict(set)
        self.by_code = collections.defaultdict(set)
        for code, t in self.terms.items():
            if t.get("param_parent"):
                self.children[t["param_parent"]].append(code)
            if "pest_parent" not in t or (code in groups and not t.get("reportable")):
                continue  # family node or a grouping such as COMPONENTS, not an analyte
            if _summed(t["name"]):
                # a summed term: its parenthesis defines it, only the full name identifies it
                self.strong[code], self.weak[code] = {compounds.canon(t["name"])}, set()
                self.named[code] = set(self.strong[code])
            else:
                forms, paren = _names(t["name"])
                others = t.get("other_names", []) + t.get("common_names", [])
                self.named[code] = _keys(forms)  # from the term's own name only
                self.strong[code] = self.named[code] | _keys([o for o in others if not _code_like(o)])
                inline = re.findall(r"(?i)\bmetabolite\s+([A-Z0-9][\w-]*\d[\w-]*)", t["name"])
                self.weak[code] = _keys([x for x in [paren] + others + inline if x and _code_like(x)])
                if paren and not _code_like(paren):
                    self.weak[code] |= _keys([paren])
            # metabolite numbers (M4, M23) repeat across substances: searchable only in the family
            generic = {k for k in self.strong[code] if GENERIC_CODE.match(k)}
            self.strong[code] -= generic
            self.named[code] -= generic
            self.weak[code] |= generic
            for k in self.strong[code]:
                self.by_strong[k].add(code)
            for k in self.weak[code]:
                self.by_code[k].add(code)

    @classmethod
    def load(cls, path: str = "data/param_components.json") -> "ComponentIndex":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def family(self, *names) -> set:
        keys = _keys([n for n in names if n])
        return self.descendants({c for c, k in self.strong.items() if k & keys})

    def descendants(self, roots) -> set:
        out, todo = set(), list(roots)
        while todo:
            code = todo.pop()
            if code not in out:
                out.add(code)
                todo.extend(self.children.get(code, []))
        return {c for c in out if c in self.strong}

    def link(self, name: str, family: set, summed: set = frozenset()) -> dict:
        forms, paren = _names(name)
        strong = _keys(forms)
        weak = _keys([paren]) if paren else set()
        lead = re.match(r"^([A-Z]{1,5}[\w-]*\d[\w-]*)\s", name)
        if lead:
            weak |= _keys([lead.group(1)])  # "M8 N-(2-hydroxymethyl-...)": the code leads the name
        if paren and _code_like(paren):
            # "kresoxim methyl (BF-490-9)": the code names the part; the head alone is the parent.
            # Within the sum or family, a single term carrying the code in its name wins.
            code = compounds.canon(paren)
            for pool, method in ((summed, "param_sum"), (family, "family")):
                hits = {c for c in pool if code and code in compounds.canon(self.terms[c]["name"])}
                if len(hits) == 1:
                    # not through _pick: its alternates by name would bring the parent back
                    (hit,) = hits
                    return {"method": method, "param_codes": [hit], "param_names": [self.terms[hit]["name"]],
                            "match": "code in name"}
        for pool, method in ((summed, "param_sum"), (family, "family")):
            hits = {c for c in pool if (self.strong[c] | self.weak[c]) & (strong | weak)}
            if hits:
                return self._pick(hits, strong, method)
        # within its own sum or family, a catalogue prefix may precede the name
        # ("RPA 202248 diketonitrile-metabolite"); only a unique hit counts
        canon_name = compounds.canon(name)
        for pool, method in ((summed, "param_sum"), (family, "family")):
            hits = {c for c in pool if (m := CODE_PREFIX.match(self.terms[c]["name"]))
                    and compounds.canon(m.group(2)) == canon_name}
            if len(hits) == 1:
                return {**self._pick(hits, strong, method), "match": "name suffix"}
        hits = set().union(*(self.by_strong.get(k, set()) for k in strong))
        if hits:
            return self._pick(hits, strong, "global")
        # a code (THPI, M4, BH 518-2) outside the family counts only if a single term carries it
        codes = [c for k in (strong | weak) if (_code_like(name) or paren) and not GENERIC_CODE.match(k)
                 for c in [self.by_code.get(k, set())] if len(c) == 1]
        if codes:
            return self._pick(set().union(*codes), strong, "global_code")
        return {"method": "none", "param_codes": []}

    def _pick(self, codes: set, keys: set, method: str) -> dict:
        # alternates from outside the pool must carry the part's name in their own name: PARAM's
        # otherNames are not reliable enough (Penflufen lists "N-acetylglufosinate")
        outside = {c for c in set().union(*(self.by_strong.get(k, set()) for k in keys)) - codes
                   if self.named[c] & keys}
        named = {c for c in codes if self.named[c] & keys} | outside
        # every code carrying the part's own name reports it (Phthalimide; "Phthalimide, expressed
        # as folpet"; "Carbofuran, 3-hydroxy" and "3-OH-carbofuran ..., expressed as carbofuran");
        # several codes that only share a code or a weaker alias are a real ambiguity
        best = named or codes
        out = {"method": method if named or len(best) == 1 else f"{method}_ambiguous",
               "param_codes": sorted(best)}
        out["param_names"] = [self.terms[c]["name"] for c in out["param_codes"]]
        return out

    def describe(self, definition: str, link: dict, residue_name: str = "", parsed=None) -> list:
        """Parts of `definition` with their PARAM codes. `parsed` is another reading of the text
        in parts() form (rd_bridge.model_parts); the linking is the same either way."""
        anchor, found = parsed if parsed is not None else parts(definition)
        found = [dict(p) for p in found]
        head = re.split(r"\s*[(:]", compounds.MARKERS.sub("", residue_name))[0].strip()
        # the family comes from the text, never from a model reading's own "expressed as"
        family = self.family(parts(definition)[0] if parsed is not None else anchor, head)
        trusted = link.get("method") not in (None, "near", "none", "ambiguous") and link.get("param_codes")
        # PARAM sometimes files the parts directly under the summed term: the strongest evidence.
        # Only for a real sum: under a single substance PARAM files other residues (kresoxim-methyl
        # -> its metabolite BF-490-9), which are not parts of this definition.
        several = sum(p["role"] in ("analyte", "group") for p in found) > 1
        summed = (self.descendants(link["param_codes"]) - set(link["param_codes"])
                  if trusted and several else set())
        previous = None
        for p in found:
            if p["role"] != "analyte":
                continue
            if parsed is not None and not _grounded(p["name"], definition):
                # a model-read name must be built from words of the text ("aldicarb sulfoxide" from
                # "aldicarb, its sulfoxide"); a misread name ("Glyphosate", or IM-2-1 in a plain
                # acetamiprid definition) stays unlinked
                p.update(method="none", param_codes=[], unlinked="model name not in the text")
            else:
                p.update(self.link(p["name"], family, summed))
            if p["method"] == "none" and not several and trusted and "unlinked" not in p:
                # a single-substance definition (qualifiers such as "its salts" aside): its own
                # link is its only part
                p.update(method="definition", param_codes=link["param_codes"])
            offered = p.pop("param_name", None)
            if offered:
                # the model named the family term it takes this part to be (rd_bridge.model_parts)
                named = sorted(c for c in family | summed if self.terms[c]["name"] == offered)
                if p["method"] == "none" and len(named) == 1 and "unlinked" not in p:
                    # never for a name already rejected as not written in the text
                    p.update(method="model", param_codes=named, param_names=[offered])
                elif p["param_codes"] and named:
                    # where the rules link too, keep the model's answer: that is how it is measured
                    p["model_agrees"] = set(named) <= set(p["param_codes"])
                    if not p["model_agrees"]:
                        p["model_named"] = named
            if p.pop("included", False) and previous and previous.get("param_codes"):
                # "dichlorprop including dichlorprop-P": measuring the including substance covers it
                p["covered_by"] = previous["param_codes"]
            else:
                previous = p
        by_name = {compounds.canon(p["name"]): p for p in found if p["role"] == "analyte"}
        for p in found:
            p.pop("included", None)
            host = by_name.get(compounds.canon(p.pop("included_in", None) or ""))
            # only where the text itself says that one substance includes another
            if host is not None and host is not p and host.get("param_codes") and INCLUDES.search(definition):
                p["covered_by"] = host["param_codes"]  # "X including Y", as read by the model
        return [{k: v for k, v in p.items() if v not in ([], None) or k == "param_codes"} for p in found]


INCLUDES = re.compile(r"\bincl(?:udes?|uding|\.)?\b", re.I)


def _words(text: str) -> list:
    return re.findall(r"[a-z0-9]+", re.sub(r"sulph", "sulf", text.lower()))


def _grounded(name: str, text: str) -> bool:
    """Every word of `name` is a word of `text`, up to a plural or a short ending."""
    words = _words(text)

    def found(w):
        # equal, or the same word with a different ending of at most two letters
        # ("sulfones"/"sulfone", "sulfoxid"/"sulfoxide"), never a longer name ("Methoxychlorolefin")
        return any(w == t or t == w + "s" or w == t + "s"  # "salt" in "salts"
                   or (min(len(w), len(t)) >= 6 and abs(len(w) - len(t)) <= 2
                       and w[:min(len(w), len(t)) - 2] == t[:min(len(w), len(t)) - 2])
                   for t in words)

    return all(found(w) for w in _words(name))


def completeness(entry: dict, analysed) -> dict:
    """Did the analysed PARAM codes cover this definition (an entry with `components`)?

    complete: the summed code, or every analyte and no group part, was analysed;
    partial: some parts were, listed with what is missing;
    undetermined: everything with a PARAM code was analysed, the rest has none (or is a group);
    not_covered: nothing of it was analysed.
    """
    analysed = set(analysed)
    # only a trusted, unambiguous link is the summed code (ambiguous candidates are not equivalents)
    summed = set(entry.get("param_codes", [])) if entry.get("method") not in ("near", "none", "ambiguous") else set()
    if summed & analysed:
        return {"status": "complete", "via": "summed code", "param_codes": sorted(summed & analysed)}
    needed = [p for p in entry.get("components", []) if p["role"] in ("analyte", "group")]
    covered = [p for p in needed if set(p.get("param_codes", []) + p.get("covered_by", [])) & analysed]
    missing = [p for p in needed if p not in covered]
    unknown = [p for p in missing if p["role"] == "group" or not p.get("param_codes")]

    def label(p):
        return {"name": p.get("name") or p["text"], "param_codes": p.get("param_codes", [])}

    if needed and not missing:
        return {"status": "complete", "via": "components", "covered": [label(p) for p in covered]}
    if not covered:
        return {"status": "not_covered", "missing": [label(p) for p in missing]}
    status = "undetermined" if len(unknown) == len(missing) else "partial"
    out = {"status": status, "covered": [label(p) for p in covered], "missing": [label(p) for p in missing]}
    if unknown:
        out["without_param_code"] = [label(p) for p in unknown]
    return out
