"""Minimal LLM client (standard library only, no SDKs needed).

Providers (first one with a key is the default):
  claude  Anthropic Messages API            ANTHROPIC_API_KEY   (paid)
  openai  OpenAI Chat Completions           OPENAI_API_KEY      (paid)
  gemini  Google Gemini, OpenAI-compatible  GEMINI_API_KEY      (free tier via Google AI Studio)
  groq    Groq, OpenAI-compatible           GROQ_API_KEY        (free tier, open models)

Model names are configurable because they change over time:
  RESULTWISE_CLAUDE_MODEL / RESULTWISE_CLAUDE_FAST_MODEL / RESULTWISE_OPENAI_MODEL /
  RESULTWISE_GEMINI_MODEL / RESULTWISE_GROQ_MODEL

Current Claude models reject `temperature`, so we never send it to any provider.
Free tiers have low rate limits: requests are retried with back-off when a provider says "too many requests".
Free tiers may also use your prompts to improve their models. ONLY ever send synthetic text through this.
"""
import json
import os
import time
import urllib.error
import urllib.request

CLAUDE_MODEL = os.getenv("RESULTWISE_CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_FAST_MODEL = os.getenv("RESULTWISE_CLAUDE_FAST_MODEL", "claude-haiku-5-5")

# OpenAI-compatible providers: (base URL, key env var, default model, max-tokens field name)
COMPAT = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY",
               os.getenv("RESULTWISE_OPENAI_MODEL", "gpt-4.1-mini"), "max_completion_tokens"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
               os.getenv("RESULTWISE_GEMINI_MODEL", "gemini-3.8-flash"), "max_tokens"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY",
             os.getenv("RESULTWISE_GROQ_MODEL", "llama-3.3-70b-versatile"), "max_completion_tokens"),
}
KEY_ENV = {"claude": "ANTHROPIC_API_KEY", **{k: v[1] for k, v in COMPAT.items()}}
AI_ENGINES = ("claude", "openai", "gemini", "groq")
FREE_ENGINES = ("gemini", "groq")


class LLMError(RuntimeError):
    pass


def is_ai(engine: str) -> bool:
    return engine in AI_ENGINES


def model_name(engine: str) -> str:
    return CLAUDE_MODEL if engine == "claude" else COMPAT[engine][2] if engine in COMPAT else "offline rules"


def available_key(provider: str, key: str | None = None) -> str | None:
    if key:
        return key
    env = KEY_ENV.get(provider)
    return os.getenv(env) if env else None


def default_engine() -> str:
    """First provider with a key configured (Claude, OpenAI, Gemini, Groq), else the offline rules."""
    for e in AI_ENGINES:
        if os.getenv(KEY_ENV[e]):
            return e
    return "offline"


def _post(url: str, headers: dict, payload: dict, timeout: int = 120, retries: int = 3) -> dict:
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={**headers, "content-type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:400]
            if e.code in (429, 500, 502, 503, 529) and attempt < retries:
                wait = float(e.headers.get("retry-after") or 0) or 2 * (2 ** attempt)
                time.sleep(min(wait, 20))
                continue
            raise LLMError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"Network error: {e.reason}") from e
        except TimeoutError as e:
            raise LLMError("The AI service timed out.") from e
    raise LLMError("The AI service kept refusing requests (rate limit).")


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
    if provider in COMPAT:
        base, _env, model, max_field = COMPAT[provider]
        payload = {"model": model, max_field: max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode and provider == "openai":
            payload["response_format"] = {"type": "json_object"}
        data = _post(f"{base}/chat/completions", {"authorization": f"Bearer {key}"}, payload)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"Unexpected reply from {provider}.") from e
        if not text.strip():
            raise LLMError(f"Empty reply from {provider}.")
        return text
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
