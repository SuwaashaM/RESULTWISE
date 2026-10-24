"""Minimal LLM client (standard library only, no SDKs needed).

Providers: "claude" (Anthropic Messages API, the default) or "openai" (Chat Completions API).
Keys come from environment variables / Streamlit secrets, or the app sidebar (kept in memory only):
  ANTHROPIC_API_KEY, OPENAI_API_KEY
Model names are configurable because they change over time:
  RESULTWISE_CLAUDE_MODEL       (default claude-sonnet-5-5: report reading)
  RESULTWISE_CLAUDE_FAST_MODEL  (default claude-haiku-5-5: translation, easy-read, back-translation)
  RESULTWISE_OPENAI_MODEL

Note: current Claude models reject `temperature`, so we never send it.

ONLY ever send synthetic text through this. Real patient data must not go to an external API
without a contract, a DPIA and information-governance approval.
"""
import json
import os
import urllib.error
import urllib.request

CLAUDE_MODEL = os.getenv("RESULTWISE_CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_FAST_MODEL = os.getenv("RESULTWISE_CLAUDE_FAST_MODEL", "claude-haiku-5-5")
OPENAI_MODEL = os.getenv("RESULTWISE_OPENAI_MODEL", "gpt-4.1-mini")


class LLMError(RuntimeError):
    pass


def available_key(provider: str, key: str | None = None) -> str | None:
    if key:
        return key
    return os.getenv("ANTHROPIC_API_KEY") if provider == "claude" else os.getenv("OPENAI_API_KEY")


def default_engine() -> str:
    """Claude if a key is configured, then OpenAI, else the offline rules."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "offline"


def _post(url: str, headers: dict, payload: dict, timeout: int = 120) -> dict:
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
    except TimeoutError as e:
        raise LLMError("The AI service timed out.") from e


def complete(provider: str, system: str, user: str, key: str | None = None,
             max_tokens: int = 4000, json_mode: bool = False, fast: bool = False) -> str:
    key = available_key(provider, key)
    if not key:
        raise LLMError(f"No API key for {provider}.")
    if provider == "claude":
        data = _post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            {"model": CLAUDE_FAST_MODEL if fast else CLAUDE_MODEL, "max_tokens": max_tokens,
             "system": system, "messages": [{"role": "user", "content": user}]},
        )
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        if not text.strip():
            raise LLMError(f"Empty reply from Claude (stop_reason={data.get('stop_reason')}).")
        return text
    if provider == "openai":
        payload = {"model": OPENAI_MODEL, "max_completion_tokens": max_tokens,
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
