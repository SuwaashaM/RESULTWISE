"""Minimal LLM client (standard library only, no SDKs needed).

Providers: "claude" (Anthropic Messages API) or "openai" (Chat Completions API).
Keys come from environment variables or are passed in from the app sidebar (kept in memory only).
Model names are configurable because they change over time:
  RESULTWISE_CLAUDE_MODEL  (default below)
  RESULTWISE_OPENAI_MODEL  (default below)

ONLY ever send synthetic text through this. Real patient data must not go to an external API
without a contract, a DPIA and information-governance approval.
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_CLAUDE_MODEL = os.getenv("RESULTWISE_CLAUDE_MODEL", "claude-sonnet-5-5")
DEFAULT_OPENAI_MODEL = os.getenv("RESULTWISE_OPENAI_MODEL", "gpt-4.1-mini")


class LLMError(RuntimeError):
    pass


def available_key(provider: str, key: str | None = None) -> str | None:
    if key:
        return key
    return os.getenv("ANTHROPIC_API_KEY") if provider == "claude" else os.getenv("OPENAI_API_KEY")


def _post(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={**headers, "content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:400]
        raise LLMError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"Network error: {e.reason}") from e


def complete(provider: str, system: str, user: str, key: str | None = None,
             max_tokens: int = 1500, json_mode: bool = False) -> str:
    key = available_key(provider, key)
    if not key:
        raise LLMError(f"No API key for {provider}.")
    if provider == "claude":
        data = _post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            {"model": DEFAULT_CLAUDE_MODEL, "max_tokens": max_tokens, "temperature": 0,
             "system": system, "messages": [{"role": "user", "content": user}]},
        )
        return "".join(block.get("text", "") for block in data.get("content", []))
    if provider == "openai":
        payload = {"model": DEFAULT_OPENAI_MODEL, "temperature": 0, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = _post("https://api.openai.com/v1/chat/completions", {"authorization": f"Bearer {key}"}, payload)
        return data["choices"][0]["message"]["content"]
    raise LLMError(f"Unknown provider {provider}")


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (tolerates code fences or stray prose)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("Model reply contained no JSON object.")
    return json.loads(text[start:end + 1])
