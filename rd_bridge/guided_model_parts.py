"""Source-grounded LLM interpretation of EU residue definitions.

Unlike the baseline data/model_parts.json cache this module makes official
guidance an actual input to every model call. Source summaries are versioned in
data/interpretation_guidance.json and selected by RD wording/scope. The model
reads the EU text; the downstream PARAM linker stays deterministic.

The independent cache prevents a guidance change from invalidating ~765 prior
Haiku answers. New/change-only refreshes automatically use the guided reader.
Previously interpreted RDs are never replaced without a separate reviewed PR.

Usage:
    python -m rd_bridge.guided_model_parts --scope new --max-calls 40
    python -m rd_bridge.guided_model_parts --scope selected --ids 253,301 --max-calls 6 --output reports/experiment.json
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import sys

from rd_bridge import components, llm, model_parts

ROOT = Path(__file__).resolve().parent.parent
GUIDANCE_PATH = ROOT / "data" / "interpretation_guidance.json"
CACHE = ROOT / "data" / "guided_model_parts.json"
PROMPT_VERSION = "guided-rd-v1"
SYSTEM_ADDENDUM = """
SOURCE-GROUNDED INTERPRETATION. The EU definition is controlling.
The following evidence notes are reviewed paraphrases of OECD, EU and EFSA
documents, NOT a new legal definition. Use the selected evidence to interpret
the exact residue text. Where general heuristics above conflict with explicit
EU wording or guidance, prefer the source evidence.
Important distinctions:
1. The heading names the pesticide/definition and may not be a measured part.
2. 'expressed as X' gives the reporting/conversion basis; it DOES NOT itself
   require X as a separately measured analyte. The reported unit may differ
   from the measured substance.
3. Separately named constituents in a 'sum of' definition are real components;
   never drop them just because the sum is expressed as the parent.
4. 'determined as' may identify a single measured conversion product: do not
   invent the precursors as separately measured analytes unless the definition
   explicitly requires their enumeration. Preserve unenumerated groups.
5. A named alternative residue triggered by 'where only ...' is conditional;
   do not add its constituents to the unconditional main definition.
6. PARAM names in the prompt are possible reference links, not evidence that
   their listed terms must be measured. A whole-RD code is not a component.
Do not solve uncertainties by guessing. Return only what the legal text
supports, with notes for qualifiers and expressed_as kept separate.
"""

def catalogue(path=GUIDANCE_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported guidance schema version")
    ids = [rule["id"] for rule in data["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Guidance rule IDs must be unique")
    for rule in data["rules"]:
        if not rule.get("sources") or any(s not in data["sources"] for s in rule["sources"]):
            raise ValueError("Guidance rule without real source: " + rule["id"])
    return data


def guidance_hash(data=None):
    data = data or catalogue()
    return hashlib.sha256(json.dumps(data, ensure_ascii=False,
                                      sort_keys=True).encode("utf-8")).hexdigest()[:16]


def prompt_hash(data=None):
    data = data or catalogue()
    payload = [model_parts.SYSTEM, SYSTEM_ADDENDUM, model_parts.SCHEMA,
               PROMPT_VERSION, guidance_hash(data)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                      ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def select(definition, *, is_exception=False, data=None):
    """Deterministic evidence retrieval from a curated source index."""
    data = data or catalogue()
    lowered = definition.casefold()
    chosen = []
    for rule in sorted(data["rules"], key=lambda x: x["priority"]):
        if (rule.get("always")
                or (is_exception and rule["id"] == "OECD-COMMODITY-VARIANTS")
                or any(token.casefold() in lowered for token in rule.get("patterns", []))):
            chosen.append(rule)
    return chosen


def render(definition, *, is_exception=False, data=None):
    data = data or catalogue()
    rules = select(definition, is_exception=is_exception, data=data)
    lines = []
    for rule in rules:
        refs = "; ".join(
            f"{key}: {data['sources'][key]['title']} ({data['sources'][key]['url']})"
            for key in rule["sources"])
        lines += [f"[{rule['id']}] {rule['principle']}",
                  f"  Evidence location: {rule['locator']}. Sources: {refs}."]
    return "\n".join(lines), [r["id"] for r in rules]


def contextual_hash(names, selected_ids, guide_digest):
    return hashlib.sha256(json.dumps([names, selected_ids, guide_digest],
                                      ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def ask(definition, names, *, is_exception=False, data=None, caller=llm.call):
    data = data or catalogue()
    guidance, ids = render(definition, is_exception=is_exception, data=data)
    family = "\n".join("- " + n for n in names) or "(none)"
    prompt = (f"Authoritative EU residue definition:\n{definition}\n\n"
              "Relevant source-backed interpretation principles "
              "(selected for this definition):\n" + guidance
              + "\n\nCandidate EFSA PARAM family names (for reference only, "
                "not extra required analytes):\n" + family)
    response = model_parts.clean(
        caller(model_parts.SYSTEM + "\n\n" + SYSTEM_ADDENDUM, prompt,
               model_parts.SCHEMA), names)
    return {**response,
            "context": model_parts.context_hash(names),
            "guidance_context": contextual_hash(names, ids, guidance_hash(data)),
            "guidance_ids": ids,
            "guidance_version": guidance_hash(data),
            "prompt_variant": PROMPT_VERSION}


def load(path=CACHE, *, data=None):
    data = data or catalogue()
    path = Path(path)
    if not path.is_file():
        return {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    if (saved.get("model") != llm.MODEL
            or saved.get("prompt") != prompt_hash(data)
            or saved.get("guidance_version") != guidance_hash(data)):
        return {}
    return saved.get("definitions", {})


def save(answers, path=CACHE, *, data=None):
    data = data or catalogue()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "model": llm.MODEL, "prompt": prompt_hash(data),
        "guidance_version": guidance_hash(data),
        "definitions": answers,
    }, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sources_for(rows):
    """Identify current definitions and exception scopes for prompt selection."""
    meta = {}
    for row in rows:
        for d in [row["default"], *row["exceptions"]]:
            entry = meta.setdefault(d["definition"], {"names": [], "is_exception": False})
            if row["name"] not in entry["names"]:
                entry["names"].append(row["name"])
            entry["is_exception"] |= bool(d.get("commodity_codes"))
    return meta


def contexts(rows, index):
    meta = sources_for(rows)
    return {text: {**entry, "family": model_parts.context(index, text, entry["names"])}
            for text, entry in meta.items()}


def valid(answer, definition, ctx, data=None):
    data = data or catalogue()
    ids = [r["id"] for r in select(definition, is_exception=ctx["is_exception"], data=data)]
    return (answer.get("prompt_variant") == PROMPT_VERSION
            and answer.get("context") == model_parts.context_hash(ctx["family"])
            and answer.get("guidance_version") == guidance_hash(data)
            and answer.get("guidance_context") ==
                contextual_hash(ctx["family"], ids, guidance_hash(data))
            and answer.get("guidance_ids") == ids)


def choose_todo(current_contexts, baseline_answers, guided_answers, *,
                scope="new", selected_ids=None, rows=None, data=None):
    """'new' never re-asks a valid old reading; 'selected' is explicit opt-in."""
    data = data or catalogue()
    wanted = set(current_contexts)
    if scope == "selected":
        if rows is None or not selected_ids:
            raise ValueError("selected scope needs --ids and reference rows")
        targets = {int(rid) for rid in selected_ids}
        wanted = {e["definition"] for r in rows if r["residue_id"] in targets
                  for e in [r["default"], *r["exceptions"]]}
        missing = targets - {r["residue_id"] for r in rows}
        if missing:
            raise ValueError("Unknown RD IDs: " + repr(sorted(missing)))
    elif scope != "new":
        raise ValueError("scope must be new or selected")
    out = []
    for definition in sorted(wanted):
        ctx = current_contexts[definition]
        if valid(guided_answers.get(definition, {}), definition, ctx, data):
            continue
        if scope == "new" and baseline_answers.get(definition, {}).get("context") == model_parts.context_hash(ctx["family"]):
            continue
        out.append(definition)
    return out


def refresh(todo, ctxs, answers, *, workers=4, data=None, caller=llm.call):
    data = data or catalogue()
    errors = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(ask, t, ctxs[t]["family"],
                             is_exception=ctxs[t]["is_exception"],
                             data=data, caller=caller): t for t in todo}
        for future in concurrent.futures.as_completed(tasks):
            t = tasks[future]
            try:
                answers[t] = future.result()
            except (llm.LLMError, ValueError, TypeError, KeyError) as exc:
                errors[t] = f"{type(exc).__name__}: {exc}"
    return answers, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scope", choices=("new", "selected"), default="new")
    parser.add_argument("--ids", help="Comma-separated RD IDs for selected scope")
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=CACHE)
    args = parser.parse_args()
    if args.max_calls < 1 or args.workers < 1:
        parser.error("max-calls and workers must be positive")
    rows = json.loads((ROOT / "data" / "residue_param_map.json").read_text(encoding="utf-8"))
    index = components.ComponentIndex.load(str(ROOT / "data" / "param_components.json"))
    ctxs = contexts(rows, index)
    data = catalogue()
    previous = model_parts.load()
    answers = {t: a for t, a in load(args.output, data=data).items()
               if t in ctxs and valid(a, t, ctxs[t], data)}
    ids = [int(v) for v in args.ids.split(",")] if args.ids else None
    todo = choose_todo(ctxs, previous, answers, scope=args.scope,
                       selected_ids=ids, rows=rows, data=data)
    if len(todo) > args.max_calls:
        parser.error(f"{len(todo)} uncached definitions exceed --max-calls={args.max_calls}; "
                     "refusing an unbounded paid run")
    if args.scope == "new" and args.output.resolve() != CACHE.resolve():
        parser.error("new-scope writes must target the standard guided cache")
    if todo and not __import__("os").environ.get("ANTHROPIC_API_KEY"):
        parser.error("ANTHROPIC_API_KEY is required for new guided interpretations")
    if not todo and not answers:
        # A fresh repository with a valid existing baseline has no new RD text
        # to interpret. Avoid proposing a meaningless empty guided cache in
        # every EU data refresh (and do not touch any prior saved files).
        print(f"{llm.MODEL} ({PROMPT_VERSION}): 0 calls, no guided results; "
              "cache unchanged")
        return
    answers, errors = refresh(todo, ctxs, answers, workers=args.workers, data=data)
    save(answers, args.output, data=data)
    print(f"{llm.MODEL} ({PROMPT_VERSION}): {len(ctxs)} definitions, "
          f"{len(todo)} calls, {len(errors)} failed, {len(answers)} guided cached "
          f"-> {args.output}")
    for definition, msg in sorted(errors.items()):
        print(f"FAILED {definition[:100]}: {msg}", file=sys.stderr)
    if errors:
        raise SystemExit("One or more guided interpretations failed: review the partial cache")


if __name__ == "__main__":
    main()
