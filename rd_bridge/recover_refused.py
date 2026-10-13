"""Recover one documented Anthropic refusal without repeating 764 prior calls.

Haiku refused the verbatim EU name "Verticillium albo-atrum isolate WCS850"
in a completed full reread run. Sonnet gets the SAME source-backed prompt.
If Sonnet also refuses, retain the exact EU organism label as a separately
flagged deterministic reading. Do not label this exception as model-produced.

No special chemical identity or PARAM code is fabricated.
"""
import argparse
import json
from pathlib import Path

from rd_bridge import components, guided_model_parts, llm, model_parts

NAME = "Verticillium albo-atrum isolate WCS850"
SONNET = "claude-sonnet-5-5"


def exact_fallback(definition, context, *, data=None):
    """Explicit source-literal fallback for this one existing EU microorganism.

    The original public EU text names a single biological isolate without
    sums, conversions, metabolites or group qualifiers. This is not an LLM
    answer and MUST be visible as such in the rebuilt mapping.
    """
    if definition != NAME:
        raise ValueError("Exact fallback is limited to the verified EU isolate name")
    data = data or guided_model_parts.catalogue()
    selected = guided_model_parts.select(
        definition, is_exception=context["is_exception"], data=data)
    ids = [r["id"] for r in selected]
    version = guided_model_parts.guidance_hash(data)
    return {
        "expressed_as": None,
        "parts": [{"name":NAME,"role":"analyte"}],
        "context": model_parts.context_hash(context["family"]),
        "guidance_context": guided_model_parts.contextual_hash(
            context["family"], ids, version),
        "guidance_ids": ids,
        "guidance_version": version,
        "prompt_variant": guided_model_parts.PROMPT_VERSION,
        "interpretation_source": "exact_EU_literal_fallback",
        "model_used": "none",
        "requires_followup": True,
        "fallback_reason": "Haiku and Sonnet refused this plain EU biological-isolate name; "
                           "original EU text retained exactly, no PARAM code invented.",
    }


def sonnet_caller(system, prompt, schema):
    return llm.call(system, prompt, schema, model=SONNET, max_tokens=5000, retries=3)


def complete_shard(shard_path, rows, index, *, caller=sonnet_caller):
    shard_path = Path(shard_path)
    contexts = guided_model_parts.contexts(rows, index)
    if NAME not in contexts:
        raise ValueError("Source no longer contains the expected isolate")
    answers = guided_model_parts.load(shard_path)
    expected_shard = guided_model_parts.in_shard(
        sorted(contexts), contexts, 5, 16)
    missing = [t for t in expected_shard if not guided_model_parts.valid(
        answers.get(t, {}), t, contexts[t])]
    if missing != [NAME]:
        raise ValueError(
            f"Recovery expected one refused EU isolate; missing {len(missing)}: "
            f"{missing[:5]}")
    ctx = contexts[NAME]
    try:
        answer = guided_model_parts.ask(
            NAME, ctx["family"], is_exception=ctx["is_exception"],
            caller=caller)
        answer.update(interpretation_source="model", model_used=SONNET)
    except llm.LLMError as exc:
        if "stop_reason refusal" not in str(exc):
            raise
        answer = exact_fallback(NAME, ctx)
    answers[NAME] = answer
    guided_model_parts.save(answers, shard_path)
    if len(answers) != len(expected_shard):
        raise ValueError("Recovered shard does not contain its complete assigned set")
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shard", type=Path, default=Path("shards/guided-5.json"))
    args = parser.parse_args()
    root = guided_model_parts.ROOT
    rows = json.loads((root / "data" / "residue_param_map.json").read_text(encoding="utf-8"))
    index = components.ComponentIndex.load(str(root / "data" / "param_components.json"))
    result = complete_shard(args.shard, rows, index)
    print(f"Recovered {NAME}; interpretation_source="
          f"{result.get('interpretation_source')}; "
          f"model_used={result.get('model_used')}; previous 47 answers preserved.")


if __name__ == "__main__":
    main()
