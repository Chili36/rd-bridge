"""One structured call to the Anthropic Messages API, standard library only.

The reply is constrained to a JSON schema with structured outputs (output_config.format), so it
is JSON that matches the schema. Forcing a tool instead does not work on every model: Sonnet 5.5
rejects tool_choice "tool" with HTTP 400. The key comes from ANTHROPIC_API_KEY (a GitHub Actions
repository secret in CI).
"""
import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MODEL = os.environ.get("RD_BRIDGE_MODEL") or "claude-haiku-5-5"  # e.g. claude-sonnet-5-5
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


class LLMError(RuntimeError):
    pass


def call(system: str, prompt: str, schema: dict, model: str = MODEL, max_tokens: int = 16000,
         retries: int = 5) -> dict:
    """Return the JSON object the model produced for `prompt`, matching `schema`."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    body = json.dumps({
        # no temperature/top_p/top_k: Haiku 5.5 and Sonnet 5.5 reject them with HTTP 400.
        # max_tokens leaves room for the adaptive thinking both models run by default.
        "model": model, "max_tokens": max_tokens, "system": system,
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    headers = {"x-api-key": key, "anthropic-version": API_VERSION, "content-type": "application/json"}
    for attempt in range(retries + 1):
        request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=300) as resp:
                reply = json.load(resp)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == retries:
                raise LLMError(f"HTTP {exc.code}: {exc.read()[:500]!r}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries:
                raise LLMError(str(exc)) from exc
        time.sleep(min(60, 2 ** attempt))
    stop = reply.get("stop_reason")
    if stop in ("refusal", "max_tokens"):
        raise LLMError(f"stop_reason {stop}: the answer may not match the schema")
    text = "".join(b.get("text", "") for b in reply.get("content", []) if b.get("type") == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"reply is not JSON (stop_reason {stop}): {text[:200]!r}") from exc
