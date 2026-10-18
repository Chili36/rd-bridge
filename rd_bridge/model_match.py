"""Ask a model for the PARAM term of definitions the deterministic matcher cannot link.

`rd_bridge.match` links only on hard evidence (exact text, spelling table, constituent set, CAS,
alias). Many unlinked EU definitions still have an obvious PARAM term under other wording
("Chlorate" / "Chlorates", "Indolylacetic acid" / "indole-3-acetic acid", a PARAM name cut off at
its field length). For each such definition this module shortlists PARAM pesticide terms and asks
the model for its best guess, or none when no candidate is the same substance or residue.

Answers are cached in data/model_matches.json for one model and prompt; `rd_bridge.match` applies
them as `method: "model"`, with the model's reason and confidence in `evidence`. Rule links are
never replaced, and verified catalogue gaps (`catalogue_gap`) keep their legal decision.

Usage: python -m rd_bridge.model_match [--max-calls 200] [--dry-run]
Reads data/residue_param_map.json (run rd_bridge.match first) and data/param_pest_terms.json.
"""
import argparse
import difflib
import functools
import hashlib
import heapq
import json
import os
import re
import sys

from rd_bridge import compounds, llm

CACHE = "data/model_matches.json"
MODEL = "claude-sonnet-5-5"
UNLINKED = {"none", "near", "ambiguous"}
SHORTLIST = 20

SYSTEM = """You map EU pesticide residue definitions (Regulation (EC) No 396/2005, EU Pesticides \
Database wording) to EFSA PARAM catalogue terms used to report pesticide monitoring results.

You get one EU residue definition and a shortlist of PARAM pesticide terms. Choose the term an \
experienced EFSA data reporter would use to report a result for that definition.

Make a good guess. These differences do NOT stop a match:
- spelling, punctuation, hyphens, singular/plural, British/American spelling, synonyms and \
systematic vs common names of the same substance
- a PARAM name that is cut off, abbreviated, or adds or omits a chemical name in brackets
- small wording differences in the same residue, e.g. "and its salts", "free and conjugated", \
"sum of isomers", "expressed as X", when the same substance is clearly meant
- an EU cross-reference ("Metam (see methylisothiocyanate)") pointing at the PARAM term

Return no code only when no candidate is the same substance or residue, for example:
- a different chemical (penconazole is not ipconazole; phosphoric acid is not phosphonic acid)
- a different microorganism strain or isolate (strain codes identify different active substances)
- a different stated CAS number for an oil or mixture
- the EU definition is a metabolite and the only candidate is the parent, or the reverse

Confidence: high = same substance and same residue; medium = same substance, residue wording \
differs; low = plausible but uncertain. Give a one-sentence reason a reviewer can check."""

SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": ["string", "null"], "description": "PARAM code from the shortlist, or null"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reason": {"type": "string"},
    },
    "required": ["code", "confidence", "reason"],
    "additionalProperties": False,
}


def prompt_hash() -> str:
    return hashlib.sha256(json.dumps([MODEL, SYSTEM, SCHEMA, SHORTLIST], sort_keys=True).encode()).hexdigest()[:16]


def _head(text: str) -> str:
    return compounds.norm(re.split(r"\s*[(,:]", text, maxsplit=1)[0])


@functools.lru_cache(maxsize=None)
def _term_keys(name: str) -> tuple:
    """A PARAM name's head, normalised and canonical forms; the same 1391 names recur in every call."""
    return _head(name), compounds.norm(name), compounds.canon(name)


@functools.lru_cache(maxsize=None)
def _matcher(b: str) -> difflib.SequenceMatcher:
    """A SequenceMatcher keeping b's index, so only the definition side (seq1) changes per call."""
    return difflib.SequenceMatcher(None, "", b)


def _ratio(a: str, b: str, quick: bool = False) -> float:
    """difflib ratio of a and b, or with `quick` its upper bound (quick_ratio)."""
    m = _matcher(b)  # shared by every caller with this b, so set seq1 each time
    m.set_seq1(a)
    return m.quick_ratio() if quick else m.ratio()


def candidates(definition: str, terms: list, limit: int = SHORTLIST) -> list:
    """PARAM terms most like the definition: by head name, full text and head word containment."""
    key = tuple((t["code"], t["name"], t.get("pestClass")) for t in terms)
    return [{"code": code, "name": name, **({"class": cls} if cls else {})}
            for code, name, cls in _shortlist(definition, key, limit)]


@functools.lru_cache(maxsize=4096)
def _shortlist(definition: str, terms: tuple, limit: int) -> tuple:
    """`candidates` over (code, name, pestClass) terms, memoised: every match.build checks each
    cached guess's shortlist against the same catalogue.

    Terms are scored in order of their upper bound (difflib quick_ratio), and scoring stops once
    no remaining term can reach the limit-th best score; the shortlist is the same as scoring
    every term."""
    head, full = _head(definition), compounds.norm(definition)
    canon_head = compounds.canon(re.split(r"\s*[(,:]", definition, maxsplit=1)[0])
    bounded = []
    for t in terms:
        term_head, term_norm, term_canon = _term_keys(t[1])
        bump = 0.95 if len(canon_head) > 4 and canon_head in term_canon else 0.0
        pairs = [(_ratio(head, term_head, quick=True), head, term_head),
                 (_ratio(full, term_norm, quick=True), full, term_norm)]
        bounded.append((max(bump, *(ub for ub, _, _ in pairs)), bump, pairs, t))
    bounded.sort(key=lambda b: -b[0])
    best, scored = [], []  # best: min-heap of the top `limit` scores so far
    for upper, bump, pairs, t in bounded:
        if best and len(best) >= limit and upper < best[0]:
            break  # every later term's score is below the shortlist
        # The score is a ratio only where that ratio's bound exceeds the containment bump
        score = max([bump, *(_ratio(a, b) if ub > bump else 0.0 for ub, a, b in pairs)])
        scored.append((score, t))
        if len(best) < limit:
            heapq.heappush(best, score)
        elif best and score > best[0]:
            heapq.heapreplace(best, score)
    scored.sort(key=lambda s: (-s[0], s[1][0]))
    return tuple(t for _, t in scored[:limit])


def validate(answer: dict, listed: list) -> dict:
    code = answer.get("code")
    if code is not None and code not in {c["code"] for c in listed}:
        raise ValueError(f"model chose {code!r}, which is not on the shortlist")
    if answer.get("confidence") not in ("high", "medium", "low") or not str(answer.get("reason", "")).strip():
        raise ValueError("model answer needs a confidence and a reason")
    return {"code": code, "confidence": answer["confidence"], "reason": answer["reason"].strip()}


def shortlist_fingerprint(listed: list) -> str:
    return hashlib.sha256(json.dumps([[c["code"], c["name"]] for c in listed]).encode()).hexdigest()[:16]


def is_fresh(guess: dict | None, definition: str, terms: list) -> bool:
    """A cached guess counts only while the PARAM shortlist it was made from is unchanged, so a new
    catalogue that adds, renames or removes candidate terms gets the definition asked again."""
    return bool(guess) and guess.get("shortlist") == shortlist_fingerprint(candidates(definition, terms))


def ask(definition: str, terms: list) -> dict:
    listed = candidates(definition, terms)
    prompt = (f"EU residue definition:\n{definition}\n\nPARAM shortlist (code | name | class):\n"
              + "\n".join(f"{c['code']} | {c['name']} | {c.get('class', '')}" for c in listed))
    answer = validate(llm.call(SYSTEM, prompt, SCHEMA, model=MODEL, max_tokens=4000), listed)
    return {**answer, "candidates": [c["code"] for c in listed], "shortlist": shortlist_fingerprint(listed)}


def unlinked(rows: list) -> list:
    """Definition texts the rules left unlinked, excluding verified catalogue gaps, in map order."""
    seen, out = set(), []
    for r in rows:
        for d in [r["default"], *r.get("exceptions", [])]:
            text = d["definition"]
            if d.get("method") in UNLINKED and "catalogue_gap" not in d and text not in seen:
                seen.add(text)
                out.append(text)
    return out


def pending(rows: list, terms: list, cached: dict) -> list:
    return [t for t in unlinked(rows) if not is_fresh(cached.get(t), t, terms)]


def run(rows: list, terms: list, cached: dict, max_calls: int) -> tuple[dict, list]:
    """Ask for every unlinked definition without a fresh guess; refuse to start if that exceeds
    max_calls. Returns the answers and the failures."""
    todo = pending(rows, terms, cached)
    if len(todo) > max_calls:
        raise SystemExit(f"{len(todo)} definitions need a model call, more than --max-calls {max_calls}")
    answers, errors = dict(cached), []
    for text in todo:
        try:
            answers[text] = ask(text, terms)
        except (llm.LLMError, ValueError) as exc:
            errors.append(f"{text[:60]}: {exc}")
    for error in errors:
        print(f"not cached: {error}", file=sys.stderr)
    return answers, errors


def load(path: str = CACHE) -> dict:
    """{definition: guess} made with the current model and prompt."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("model") != MODEL or data.get("prompt") != prompt_hash():
        return {}
    return data.get("matches", {})


def save(matches: dict, path: str = CACHE) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"model": MODEL, "prompt": prompt_hash(), "matches": matches}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true", help="list what would be asked")
    args = parser.parse_args()
    with open("data/residue_param_map.json", encoding="utf-8") as fh:
        rows = json.load(fh)
    with open("data/param_pest_terms.json", encoding="utf-8") as fh:
        terms = json.load(fh)
    cached = load()
    todo = pending(rows, terms, cached)
    if args.dry_run:
        print(f"{len(todo)} definitions would be asked ({len(cached)} cached)")
        return
    matches, errors = run(rows, terms, cached, args.max_calls)
    save(matches)  # keep what succeeded
    asked = [t for t in todo if t in matches]
    linked = sum(1 for t in asked if matches[t]["code"])
    print(f"{MODEL}: {len(todo)} asked, {len(asked)} answered, {linked} linked, "
          f"{len(asked) - linked} no match, {len(errors)} failed")
    if errors:
        sys.exit(1)  # the refresh workflow must see an incomplete run


if __name__ == "__main__":
    main()
