"""Parse the (R) footnote of an EU residue definition into commodity-specific exceptions.

The footnotes are free text. They mix separators (newlines, literal "\\n\\r", ";"), scope
forms ("code X except Y", "codes A and B", "A/B/C", "codes from A to B") and typos in the
commodity codes ("code 100000" for 1000000, "code 500000" for 0500000). Every repair and
every doubt is written to the entry, so no exception is silently guessed.

Codes are checked against the structure of Annex I to Regulation (EC) No 396/2005:
seven digits, a known top-level group, and every "except" code nested inside an included
code. The full Annex I code list is not checked here.
"""
import re

# Top-level Annex I groups (Part A), keyed by their first two digits.
ANNEX_GROUPS = {
    "01": "fruits, fresh or frozen; tree nuts",
    "02": "vegetables, fresh or frozen",
    "03": "pulses",
    "04": "oilseeds and oil fruits",
    "05": "cereals",
    "06": "teas, coffee, herbal infusions, cocoa and carobs",
    "07": "hops",
    "08": "spices",
    "09": "sugar plants",
    "10": "products of animal origin - terrestrial animals",
    "11": "fish, fish products and other marine and freshwater food products",
    "12": "plants and plant products used exclusively for animal feed",
}

CODE = r"\d{6,7}"
SCOPE_START = re.compile(rf"\bcodes?\b|(?<![\w,.]){CODE}\b", re.I)
FIRST_CODE = re.compile(rf"(?<![\w,.])({CODE})\b")
RANGE = re.compile(rf"(?:from\s+)?({CODE})\s+to\s+({CODE})", re.I)
TRAILING_MARKERS = re.compile(r"\s*(\((F|A|R|\*|\+|\+\+)\))+\s*$")
QUOTES = "\"'“”‘’"


def level(code: str) -> int:
    """Number of significant leading digits in a 7-digit Annex I code (its hierarchy depth)."""
    for n in (2, 3, 4, 5):
        if code[n:].strip("0") == "":
            return n
    return 7


def contains(outer: str, inner: str) -> bool:
    return inner.startswith(outer[:level(outer)])


def _clean_text(footnote: str) -> str:
    text = footnote.replace("\\n", "\n").replace("\\r", "\n").replace("\r", "\n")
    return text.replace("\xad", "")


def _segments(footnote: str) -> list:
    """One string per candidate clause."""
    out = []
    for line in _clean_text(footnote).split("\n"):
        parts = line.split(";")
        clause = parts[0]
        for part in parts[1:]:
            # A ";" starts a new clause only when the next part opens its own code scope.
            if re.search(rf"{CODE}[^:]*:", part) and SCOPE_START.search(part.split(":")[0]):
                out.append(clause)
                clause = part
            else:
                clause += ";" + part
        out.append(clause)
    return [s.strip() for s in out if s.strip()]


def _codes(text: str) -> list:
    codes = []
    for m in RANGE.finditer(text):
        codes.append(("range", m.group(1), m.group(2)))
    for c in FIRST_CODE.findall(RANGE.sub(" ", text)):
        codes.append(("code", c))
    return codes


def _repair(code: str, excepted: list) -> tuple:
    """Return (7-digit code, repair note or None) for a raw code token.

    A note with "alternatives" means the repair could not be decided from the footnote.
    """
    if len(code) == 7:
        return code, None
    left, right = "0" + code, code + "0"
    valid = [c for c in (left, right) if c[:2] in ANNEX_GROUPS]
    nesting = [c for c in valid if excepted and all(contains(c, e) for e in excepted)]
    if nesting:
        return nesting[0], {"from": code, "to": nesting[0], "reason": "except codes nest inside it"}
    choice = (valid or [left])[0]
    note = {"from": code, "to": choice, "reason": "leading zero dropped"}
    if len(valid) > 1:
        note.update(reason="undecided", alternatives=valid[1:])
    return choice, note


def _expand(start: str, end: str) -> list:
    """Sibling codes from start to end, stepping at the depth of the end code."""
    n = max(level(start), level(end))
    step = 10 ** (7 - n)
    return [f"{c:07d}" for c in range(int(start), int(end) + 1, step)]


def _resolve(tokens: list, excepted: list, repairs: list) -> list:
    """Turn code and range tokens into 7-digit codes, recording every repair."""
    codes = []
    for t in tokens:
        if t[0] == "range":
            start, n1 = _repair(t[1], [])
            end, n2 = _repair(t[2], [])
            repairs += [n for n in (n1, n2) if n]
            codes += _expand(start, end)
        else:
            fixed, note = _repair(t[1], excepted)
            codes.append(fixed)
            if note:
                repairs.append(note)
    return codes


def parse_clause(segment: str):
    first = SCOPE_START.search(segment)
    if not first:
        return None
    number = FIRST_CODE.search(segment, first.start())
    if not number:
        return None
    colon = segment.find(":", number.end())
    if colon == -1:
        # "code 1020000  Sum of ..." (no colon): the scope ends after its last code.
        tail = re.match(rf"(?:[\s,/]|and|except|codes?|{CODE})*", segment[number.start():], re.I)
        colon = number.start() + tail.end()
        scope, definition = segment[first.start():colon], segment[colon:]
    else:
        scope, definition = segment[first.start():colon], segment[colon + 1:]
    included_txt, _, excluded_txt = re.sub(r"\bexcept\b", "\0", scope, count=1, flags=re.I).partition("\0")
    included_tokens = _codes(included_txt)

    repairs, issues = [], []
    excepted = _resolve(_codes(excluded_txt), [], repairs)
    included = _resolve(included_tokens, excepted, repairs)

    for r in repairs:
        if r.get("alternatives"):
            issues.append(f"{r['from']}: could be {' or '.join([r['to'], *r['alternatives']])}")
    for c in included + excepted:
        if c[:2] not in ANNEX_GROUPS:
            issues.append(f"{c}: not an Annex I group")
    for e in excepted:
        if not any(contains(i, e) for i in included):
            issues.append(f"except {e}: not inside any included code")
    if not included:
        issues.append("no included commodity code")

    definition = re.sub(r"\s+", " ", definition).strip().strip(QUOTES).strip()
    definition = TRAILING_MARKERS.sub("", definition.rstrip(". ")).strip().strip(QUOTES).strip()
    definition = re.sub(r",?\s*where:?$", "", definition).rstrip(". ")
    return {"commodity_codes": included, "except_codes": excepted, "definition": definition,
            "repairs": repairs, "issues": issues}


def parse(footnote: str) -> list:
    """Split an (R) footnote into {commodity_codes, except_codes, definition, repairs, issues}."""
    out, seen = [], set()
    for segment in _segments(footnote or ""):
        entry = parse_clause(segment)
        if not entry:
            continue  # notes such as "Metabolite 505M09 = ..." or "(*) Limit of determination"
        key = (tuple(entry["commodity_codes"]), tuple(entry["except_codes"]), entry["definition"])
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out
