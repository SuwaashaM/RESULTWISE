"""The local-model script plugs into the same extraction code without changing the app."""
import importlib

from resultwise import llm


def test_local_model_is_registered_for_this_run_only(monkeypatch):
    before = (dict(llm.COMPAT), llm.AI_ENGINES, llm.FREE_ENGINES, llm._post)
    try:
        lme = importlib.import_module("local_model_eval")
        lme.register_local_model("qwen2.5:7b")
        assert llm.is_ai("ollama") and llm.model_name("ollama") == "qwen2.5:7b"
        seen = {}
        monkeypatch.setattr(llm, "_post", lambda url, h, payload, timeout=60, retries=2:
                            seen.update(url=url, payload=payload) or {"choices": [{"message": {"content": "OK"}}]})
        assert llm.complete("ollama", "s", "u") == "OK"
        assert seen["url"].endswith("localhost:11434/v1/chat/completions")
        assert "temperature" not in seen["payload"]
    finally:
        llm.COMPAT.clear()
        llm.COMPAT.update(before[0])
        llm.KEY_ENV.pop("ollama", None)
        llm.AI_ENGINES, llm.FREE_ENGINES, llm._post = before[1], before[2], before[3]
    assert not llm.is_ai("ollama")  # the app itself is untouched
