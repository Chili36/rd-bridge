"""Split residue definitions into parts with a model; cache the answers in data/model_parts.json.

The rule parser in rd_bridge.components reads most definitions, but each review found new
phrasing it missed. Here a model reads the text instead and returns the same three roles
(analyte, group, qualifier). The answer is only a reading of the text: linking each part to
PARAM stays deterministic (ComponentIndex.link), so a misread name ends up unlinked, never
silently linked.

Answers are cached per definition text, with the model and a hash of the prompt. A changed
definition, model or prompt is asked again; everything else is reused, so a weekly run only
pays for what changed. Definitions without a valid cached answer, or whose answer names nothing to measure, fall back
to the rule parser.

Usage: python -m rd_bridge.model_parts [--workers N] [--limit N]
Reads the definitions in data/residue_param_map.json; needs ANTHROPIC_API_KEY.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys

from rd_bridge import components, compounds, llm

CACHE = "data/model_parts.json"
MAX_CONTEXT = 80  # family names offered in the prompt
ROLES = ("analyte", "group", "qualifier")
NULLABLE = {"anyOf": [{"type": "string"}, {"type": "null"}]}

SYSTEM = """You read EU pesticide residue definitions and list what has to be measured.

Return every part of the definition with one role:
- analyte: one specific substance that is measured on its own. This includes the parent, each
  named metabolite, each isomer or homologue the text lists one by one ("sum of E- and
  Z-isomers", "chain lengths of C8, C10 and C12", "p,p'- and o,p'-isomers"), and a specific
  named ester, salt or conjugate ("its methyl ester", "5-hydroxythiabendazole sulfate conjugate").
- group: a class that cannot be listed one by one ("all metabolites containing the
  3,5-dichloroaniline moiety", "compounds hydrolysable to X").
- qualifier: wording that does not add a separate measurement: "its salts", "its esters" and
  "its conjugates" when none is named, "free and conjugated", "sum of isomers" or "sum of
  constituent isomers" when no isomer is named, "at any ratio", origin notes.

Rules:
- Write each analyte as a full, self-contained name. Expand shorthand against the substance it
  refers to: "aldicarb, its sulfoxide and its sulfone" -> "aldicarb", "aldicarb sulfoxide",
  "aldicarb sulfone"; "phorate, its oxygen analogue and their sulfones" -> also "phorate
  sulfone" and "phorate oxygen analogue sulfone"; "X (sum of E- and Z-isomers)" -> "X E-isomer",
  "X Z-isomer"; listed chain lengths -> one analyte per chain length, named with the substance.
- Keep a code or alias that the text gives in parentheses with its name:
  "N-desmethyl-acetamiprid (IM-2-1)".
- "X including Y", where Y is an isomer, enantiomer or variant that a measurement of X already
  includes: Y is an analyte with included_in = X.
- An isomer or enantiomer of a listed substance is its own analyte only when the family list
  offers a term for it (E-/Z-mevinphos). Otherwise "X and its E-isomer", "its S-isomer", "sum of
  the R- and S-isomers" is a qualifier of X, and "sum of all isomers of X" means the analyte is X.
- Metabolites, degradation or reaction products "determined as", "oxidized to", "hydrolysed to"
  or "calculated as" a named substance A: A is the analyte and the products are not a group.
  Only a class with no named substance to measure is a group.
- A heading before the definition ("X (mixture of ...)") is never listed as well when the
  parentheses list the parts; it is the single analyte only when they just qualify it.
- expressed_as: the substance after "expressed as" or "calculated as", else null.
- notes: short notes that belong to one part ("free and conjugated", "sum of isomers").
- param_name: the prompt lists the PARAM catalogue terms in this substance's family. When an
  analyte is exactly the same substance as one of them, copy that term's name exactly (catalogue
  spellings differ: "Methiocarb-Sulfoxid", "Avermectin B1a, delta-8,9 isomer"). Never pick a
  term for a different isomer, enantiomer, salt, ester or metabolite, and never a summed term
  ("X (sum of ...)") for a single part. Otherwise null.
- Keep the text's own spelling, hyphens and word order, typos included. Do not correct or reword
  names ("X-sulphate" stays "X-sulphate"; "alpha- and beta-isomers" of X become "alpha-X" and
  "beta-X"); only add the substance a shorthand refers to.
- A class the text names as one substance to report ("X compounds, expressed as X") is one
  analyte with that name. A group is only a class described by a structure that cannot be listed
  ("all compounds containing the ... moiety").
Only use names that are in the text or follow directly from expanding it. Never add parts."""

# Structured outputs: every object closed (additionalProperties false), every field required,
# null where a field may be empty.
SCHEMA = {
    "type": "object",
    "properties": {
        "expressed_as": NULLABLE,
        "parts": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "full name; for a qualifier, its text"},
                "role": {"type": "string", "enum": list(ROLES)},
                "included_in": NULLABLE,
                "param_name": NULLABLE,
                "notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "role", "included_in", "param_name", "notes"],
            "additionalProperties": False,
        }},
    },
    "required": ["expressed_as", "parts"],
    "additionalProperties": False,
}


def prompt_hash() -> str:
    return hashlib.sha256(json.dumps([SYSTEM, SCHEMA], sort_keys=True).encode()).hexdigest()[:16]


def context_hash(names: list) -> str:
    return hashlib.sha256("\n".join(names).encode()).hexdigest()[:12]


def load(path: str = CACHE) -> dict:
    """{definition: answer} for answers made with the current model and prompt."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("model") != llm.MODEL or data.get("prompt") != prompt_hash():
        return {}
    return data.get("definitions", {})


def save(answers: dict, path: str = CACHE) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"model": llm.MODEL, "prompt": prompt_hash(), "definitions": answers}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)


def clean(answer: dict, names=()) -> dict:
    """Keep well-formed parts only. An answer with no analyte or group is kept too: for "Beer" or
    "Cow Milk" there is nothing to measure, and the rule parser is used instead."""
    listed = set(names)
    parts = []
    for p in answer.get("parts") or []:
        name = (p.get("name") or "").strip()
        if p.get("role") not in ROLES or not name:
            continue
        part = {"name": name, "role": p["role"]}
        if p.get("included_in") and p["role"] == "analyte":
            part["included_in"] = p["included_in"].strip()
        if p.get("param_name") and p["role"] == "analyte" and p["param_name"].strip() in listed:
            part["param_name"] = p["param_name"].strip()  # only a name that was offered
        if p.get("notes"):
            part["notes"] = [n.strip() for n in p["notes"] if n and n.strip()]
        parts.append(part)
    if not any(p["role"] in ("analyte", "group") for p in parts):
        parts = []
    expressed = (answer.get("expressed_as") or "").strip() or None
    return {"expressed_as": expressed, "parts": parts}


def ask(definition: str, names: list, caller=llm.call) -> dict:
    listed = "\n".join(f"- {n}" for n in names) or "(none)"
    prompt = f"Residue definition:\n{definition}\n\nPARAM terms in this substance's family:\n{listed}"
    return {**clean(caller(SYSTEM, prompt, SCHEMA), names), "context": context_hash(names)}


def as_parts(answer: dict, definition: str) -> tuple:
    """A cached answer in rd_bridge.components.parts() form: (anchor, [part])."""
    out = []
    for p in answer["parts"]:
        part = {"text": p["name"], "name": p["name"] if p["role"] != "qualifier" else None,
                "role": p["role"], "notes": list(p.get("notes", []))}
        for key in ("included_in", "param_name"):
            if p.get(key):
                part[key] = p[key]
        out.append(part)
    anchor = answer.get("expressed_as") or next((p["name"] for p in out if p["role"] == "analyte"), None)
    return anchor, out


def family_names(index, definition: str, residue_name: str, limit: int = MAX_CONTEXT) -> list:
    """Names of the PARAM terms in the family of the definition's substance, for the prompt."""
    anchor, _ = components.parts(definition)
    head = re.split(r"\s*[(:]", compounds.MARKERS.sub("", residue_name))[0].strip()
    codes = index.family(anchor, head)
    heads = getattr(index, "_heads", None)
    if heads is None:  # terms by the name before their parenthesis: "Diquat (sum of ...)"
        heads = index._heads = {}
        for code, term in index.terms.items():
            heads.setdefault(compounds.canon(term["name"].split(" (")[0]), set()).add(code)
    for name in filter(None, (anchor, head)):
        codes |= heads.get(compounds.canon(name), set())
    return sorted({index.terms[c]["name"] for c in codes})[:limit]


def current(answers: dict, contexts: dict) -> dict:
    """The answers for definitions still in use, made with the family names offered today."""
    return {t: a for t, a in answers.items() if t in contexts and a.get("context") == context_hash(contexts[t])}


def definitions(path: str = "data/residue_param_map.json") -> dict:
    """{definition text: [residue names]} for every default and exception definition. One text
    can stand under several residues ("Carbendazim and thiophanate-methyl, ..." under both)."""
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = {}
    for r in rows:
        for d in [r["default"], *r["exceptions"]]:
            names = out.setdefault(d["definition"], [])
            if r["name"] not in names:
                names.append(r["name"])
    return out


def context(index, definition: str, residue_names: list) -> list:
    """The family names offered for a definition: those of every residue it stands under."""
    return sorted(set().union(*(family_names(index, definition, n) for n in residue_names)))[:MAX_CONTEXT]


def refresh(contexts: dict, answers: dict, caller=llm.call, workers: int = 8) -> tuple:
    """Ask for every {text: family names} whose cached answer is missing or was made with
    other family names; return (answers, {text: error})."""
    todo = [t for t, names in contexts.items()
            if answers.get(t, {}).get("context") != context_hash(names)]
    errors = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ask, t, contexts[t], caller): t for t in todo}
        for future in concurrent.futures.as_completed(futures):
            text = futures[future]
            try:
                answers[text] = future.result()
            except (llm.LLMError, ValueError, KeyError, TypeError) as exc:
                errors[text] = str(exc)
    return answers, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, help="ask at most this many new definitions")
    args = parser.parse_args()
    index = components.ComponentIndex.load()
    texts = definitions()
    contexts = {t: context(index, t, names) for t, names in texts.items()}
    # keep only answers made with today's family names: a failed re-ask must fall back to the
    # rule parser, not leave an answer read against another family in the cache
    answers = current(load(), contexts)
    todo = [t for t in sorted(contexts) if answers.get(t, {}).get("context") != context_hash(contexts[t])]
    todo = todo[:args.limit]
    answers, errors = refresh({t: contexts[t] for t in todo}, answers, workers=args.workers)
    save(answers)
    print(f"{llm.MODEL}: {len(texts)} definitions, {len(todo)} asked, {len(errors)} failed, "
          f"{len(answers)} cached -> {CACHE}")
    for text, error in sorted(errors.items())[:20]:
        print(f"  failed: {text[:80]} ({error})", file=sys.stderr)
    if todo and len(errors) > len(todo) / 10:
        raise SystemExit("more than 10% of the calls failed")


if __name__ == "__main__":
    main()
