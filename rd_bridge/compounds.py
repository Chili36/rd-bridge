"""Read a residue definition as chemistry rather than as a string.

Three views of a name, all deterministic:

- `canon`: a spelling-insensitive key (sulphur/sulfur, phtalimide/phthalimide,
  flumioxazine/flumioxazin, desethyl/de-ethyl, "strain", "aka").
- `signature`: the set of components a definition sums, plus its anchor, the parent the
  residue is about ("expressed as X", else the head before the final parenthesis, else the first
  component). "Sum of A and B, expressed as A" and "A (sum of B and A, expressed as A)" have
  the same signature; Ipconazole and Penconazole do not, because their anchors differ.
- `aliases`: other names written into the definition itself (aka, also called, lab codes,
  E-numbers, a category prefix such as "Fatty acids:") and CAS numbers.
"""
import re
import unicodedata

SPELLING = [
    (r"sulph", "sulf"),
    (r"phtal", "phthal"),
    (r"consitutent", "constituent"),  # PARAM 17.8 typo (flucythrinate)
    (r"\bdes(?=(?:ethyl|methyl))", "de"),
    (r"\bde-(?=(?:ethyl|methyl))", "de"),
    (r"\b(aka|also called)\b", " "),
    (r"\bstrains?\b", " "),
    (r"&", " and "),
    (r"(?<=[a-z])ine\b", "in"),
    (r"(?<=[a-z])ole\b", "ol"),
]
# Greedy prefix: the last "expressed as" / "calculated (in total) as" names the anchor.
EXPRESSED = re.compile(r"^(.*?)(?:,?\s*\b(?:expressed|calculated)(?:\s+in\s+total)?\s+as\s+(?:the\s+)?)(?!.*\b(?:expressed|calculated)(?:\s+in\s+total)?\s+as\b)(.*)$", re.I)
SUM_LEAD = re.compile(r"^(?:the\s+)?sum\s+(?:of\s+)?", re.I)
SUM_TAIL = re.compile(r"\s*\(sum of\)\s*$", re.I)
SEPARATORS = re.compile(r",\s*(?:and\s+)?|\s+and\s+|\s+including\s+", re.I)
FILLER = re.compile(r"^(?:its|their|the|all)\s+(?:metabolites?\s+)?|^metabolites?\s+", re.I)
MARKERS = re.compile(r"\s*(\((F|A|R|\*|\+|\+\+)\))+\s*$")
PARENT_WORDS = {"parent", "parentcompound"}
STEREO_PREFIX = re.compile(r"^\s*\((?:\d+)?[EZRS](?:\s*,\s*\d*[EZRS])*\)[\s-]*")
CAS = re.compile(r"\bCAS(?:\s*(?:No\.?|number))?\s*:?\s*(\d{2,7}-\d{2}-\d)\b", re.I)
CODE_LIKE = re.compile(r"^(?!CAS\b)(?:[A-Z]{2,}[A-Z0-9]*|[A-Z]{1,5}[- ]?\d[\w-]*|E\d{3}[a-z]?)$")
ALIAS_PAREN = re.compile(r"\(\s*(?:aka|also called|formerly)\s+([^()]+?)\s*\)", re.I)
# PARAM writes some elements as "Sulfur (S)"; the symbol is an identifier, not part of the name.
ELEMENT_SYMBOL = re.compile(r"^([A-Za-z]+)\s*\(([A-Z][a-z]?)\)$")
ELEMENTS = {"sulfur": "S", "nitrogen": "N", "iron": "Fe", "copper": "Cu", "zinc": "Zn", "phosphorus": "P",
            "potassium": "K", "calcium": "Ca", "magnesium": "Mg", "aluminium": "Al", "aluminum": "Al",
            "boron": "B", "manganese": "Mn", "silver": "Ag", "mercury": "Hg", "cadmium": "Cd", "lead": "Pb",
            "arsenic": "As"}
E_NUMBER = re.compile(r"\s+(E\d{3}[a-z]?)\s*$", re.I)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("′", "'")
    return re.sub(r"[^a-z0-9]", "", text)


def canon(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    for pattern, repl in SPELLING:
        text = re.sub(pattern, repl, text)
    return norm(text)


def _top_level(text: str, splitter: re.Pattern) -> list:
    """Split on `splitter` only outside parentheses and brackets."""
    depth, start, out = 0, 0, []
    masked = []
    for ch in text:
        depth += ch in "([{"
        depth -= ch in ")]}"
        masked.append(ch if depth == 0 else "\0")
    masked = "".join(masked)
    for m in splitter.finditer(masked):
        out.append(text[start:m.start()])
        start = m.end()
    out.append(text[start:])
    return [s.strip() for s in out if s.strip()]


def _head_and_body(text: str) -> tuple:
    """'Head (body)' -> ('Head', 'body') for a final balanced parenthesis; else (None, text)."""
    if not text.endswith(")"):
        return None, text
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        depth += text[i] == ")"
        depth -= text[i] == "("
        if depth == 0:
            head = text[:i].strip()
            return (head, text[i + 1:-1].strip()) if head else (None, text)
    return None, text


def signature(definition: str):
    """Return (frozenset of canonical components, canonical anchor or None)."""
    text = MARKERS.sub("", definition.strip().rstrip("."))
    head, body = _head_and_body(text)
    if head and not re.search(r"\bsum\b|\band\b|expressed|including|,", body, re.I):
        body = text  # "Fluazifop (free)": the parenthesis qualifies, it does not define
        head = None
    expressed = None
    m = EXPRESSED.match(body)
    if m and m.group(2).strip():
        expressed = MARKERS.sub("", m.group(2)).strip()
        if canon(expressed) in PARENT_WORDS:
            expressed = None  # "expressed as parent": the parent is the head or first component
        body = m.group(1)
    elif m:
        body = m.group(1)  # "calculated in total as" with the name cut off
    body = SUM_TAIL.sub("", SUM_LEAD.sub("", body.strip()))
    parts = [FILLER.sub("", p).strip() for p in _top_level(body, SEPARATORS)]
    components = frozenset(canon(p) for p in parts if canon(p))
    anchor = expressed or head or (parts[0] if parts else None)
    return components, (canon(anchor) if anchor else None)


def compatible(a, b) -> bool:
    """Same set of components and the same anchor (parent substance)."""
    (ca, aa), (cb, ab) = a, b
    return bool(ca) and ca == cb and aa is not None and aa == ab


def same_parent(a: str, b: str) -> bool:
    """True when two definitions are about the same parent substance.

    Used only to gate untrusted near matches, so a plural parent (Chlorate / Chlorates) and
    a leading stereo descriptor ("(3E) 3-decen-2-one") still count as the same.
    """
    sa, sb = signature(STEREO_PREFIX.sub("", a))[1], signature(STEREO_PREFIX.sub("", b))[1]
    return sa is not None and sb is not None and sa.rstrip("s") == sb.rstrip("s")


def aliases(definition: str) -> list:
    """Other names a definition carries for itself, as (kind, text) pairs."""
    out = []
    text = MARKERS.sub("", definition.strip())
    for m in ALIAS_PAREN.finditer(text):
        out.append(("aka", m.group(1)))
    bare = re.sub(r"\s{2,}", " ", ALIAS_PAREN.sub("", text)).strip()
    element = ELEMENT_SYMBOL.match(bare)
    if element and ELEMENTS.get(canon(element.group(1))) == element.group(2):
        out.append(("name", element.group(1)))
    head, body = _head_and_body(bare)
    if head and CODE_LIKE.match(body):
        out += [("code", body), ("name", head)]
    m = E_NUMBER.search(bare)
    if m:
        out.append(("name", bare[:m.start()]))
    for sep in (":", " / "):
        if sep in bare:
            out.append(("name", bare.split(sep, 1)[1].strip()))
    if bare != text:
        out.append(("name", bare))
    return out


def cas_numbers(definition: str) -> list:
    return CAS.findall(definition)
