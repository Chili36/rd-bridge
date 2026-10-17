"""Ask a model for the PARAM term of definitions the deterministic matcher cannot link.

`rd_bridge.match` links only on hard evidence (exact text, spelling table, constituent set, CAS,
alias). Many unlinked EU definitions still have an obvious PARAM term under other wording
("Chlorate" / "Chlorates", "Indolylacetic acid" / "indole-3-acetic acid", a PARAM name cut off at
its field length). For each such definition this module shortlists PARAM pesticide terms and asks
the model for its best guess, or none when no candidate is the same substance or residue.

Answers are cached in data/model_matches.json for one model and prompt; `rd_bridge.match` applies
them as `method: "model"`, with the model's reason and confidence in `evidence`. Rule links are
never replaced, and verified catalogue gaps (`catalogue_gap`) keep their legal decision. Two checks
the model cannot override: a low-confidence guess is kept as a suggestion (`model_guess`), not a
link, and a guess is refused when the definition states a CAS number the term does not carry.

Usage: python -m rd_bridge.model_match [--max-calls 200] [--dry-run]
Reads data/residue_param_map.json (run rd_bridge.match first) and data/param_pest_terms.json.
"""
import argparse
import difflib
import hashlib
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
- the EU definition is a metabolite and the only candidate is the parent, or the reverse. A \
definition written "X (Y)" or "X (Y, expressed as X)" with Y a metabolite or derivative means Y is \
measured: a term for the parent X alone is not a match
- a broader group or genus for one named substance or organism, or an unrelated product that \
only shares a word

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


def candidates(definition: str, terms: list, limit: int = SHORTLIST) -> list:
    """PARAM terms most like the definition: by head name, full text and head word containment."""
    head, full = _head(definition), compounds.norm(definition)
    canon_head = compounds.canon(re.split(r"\s*[(,:]", definition, maxsplit=1)[0])
    scored = []
    for t in terms:
        name = t["name"]
        score = max(difflib.SequenceMatcher(None, head, _head(name)).ratio(),
                    difflib.SequenceMatcher(None, full, compounds.norm(name)).ratio())
        if len(canon_head) > 4 and canon_head in compounds.canon(name):
            score = max(score, 0.95)
        scored.append((score, t["code"], t))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [{"code": t["code"], "name": t["name"], **({"class": t["pestClass"]} if t.get("pestClass") else {})}
            for _, _, t in scored[:limit]]


def validate(answer: dict, listed: list) -> dict:
    code = answer.get("code")
    if code is not None and code not in {c["code"] for c in listed}:
        raise ValueError(f"model chose {code!r}, which is not on the shortlist")
    if answer.get("confidence") not in ("high", "medium", "low") or not str(answer.get("reason", "")).strip():
        raise ValueError("model answer needs a confidence and a reason")
    return {"code": code, "confidence": answer["confidence"], "reason": answer["reason"].strip()}


def ask(definition: str, terms: list) -> dict:
    listed = candidates(definition, terms)
    prompt = (f"EU residue definition:\n{definition}\n\nPARAM shortlist (code | name | class):\n"
              + "\n".join(f"{c['code']} | {c['name']} | {c.get('class', '')}" for c in listed))
    answer = validate(llm.call(SYSTEM, prompt, SCHEMA, model=MODEL, max_tokens=4000), listed)
    return {**answer, "candidates": [c["code"] for c in listed]}


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


def run(rows: list, terms: list, cached: dict, max_calls: int) -> dict:
    """Ask for every uncached unlinked definition; refuse to start if that exceeds max_calls."""
    todo = [t for t in unlinked(rows) if t not in cached]
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
    return answers


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
    todo = [t for t in unlinked(rows) if t not in cached]
    if args.dry_run:
        print(f"{len(todo)} definitions would be asked ({len(cached)} cached)")
        return
    matches = run(rows, terms, cached, args.max_calls)
    save(matches)
    asked = [t for t in todo if t in matches]
    linked = sum(1 for t in asked if matches[t]["code"])
    print(f"{MODEL}: {len(todo)} asked, {len(asked)} answered, {linked} linked, "
          f"{len(asked) - linked} no match, {len(todo) - len(asked)} failed")


if __name__ == "__main__":
    main()
