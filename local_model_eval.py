"""Step 2 of 1 -> 2 -> FREE: test a free, open-source model running LOCALLY on your own computer.

Nothing leaves the machine: the model runs in Ollama (https://ollama.com) on localhost.
This script does not change the app. It plugs a local model into the same extraction code and
scores it on the same held-out reports we used for Gemini and the keyword rules.

  1. Install Ollama, then download a model:   ollama pull qwen2.5:7b      (about 4.7 GB)
                                   or lighter:   ollama pull llama3.2:3b     (about 2 GB)
  2. pip install pydantic
  3. python local_model_eval.py                      # held-out set (10 reports)
     python local_model_eval.py --model llama3.2:3b  # try another model
     python local_model_eval.py --all                # also the 104 development reports (slow)

Results are printed next to the cloud (Gemini) and keyword-rule scores, and saved to local_eval_results.json.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from resultwise import llm
from resultwise.evaluate import evaluate, load_set

OLLAMA = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

# Scores we already measured on the held-out set (see README "Evaluation")
REFERENCE = {
    "Cloud model (Gemini)": {"recall": 1.00, "precision": 0.90, "urgent_recall": 1.00,
                             "timeframe_accuracy": 1.00, "urgency_accuracy": 0.89},
    "Keyword rules (offline)": {"recall": 0.22, "precision": 1.00, "urgent_recall": 0.50,
                                "timeframe_accuracy": 1.00, "urgency_accuracy": 1.00},
}
LABELS = {"recall": "Follow-ups found", "precision": "Found items that were real",
          "urgent_recall": "Urgent follow-ups found", "timeframe_accuracy": "Timeframe correct",
          "urgency_accuracy": "Urgency correct"}


def check_ollama(model: str) -> None:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=5) as r:
            names = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except (urllib.error.URLError, TimeoutError):
        raise SystemExit(f"Can't reach Ollama at {OLLAMA}. Install it from https://ollama.com and make sure it's running.")
    if not any(n == model or n.split(":")[0] == model for n in names):
        raise SystemExit(f"Model '{model}' isn't downloaded yet. Run:  ollama pull {model}\n"
                         f"Downloaded models: {', '.join(names) or 'none'}")


def register_local_model(model: str) -> None:
    """Add an 'ollama' provider to the LLM client for this run only (no files are changed)."""
    llm.COMPAT["ollama"] = (f"{OLLAMA}/v1", "OLLAMA_API_KEY", model, "max_tokens")
    llm.KEY_ENV["ollama"] = "OLLAMA_API_KEY"
    llm.AI_ENGINES = llm.AI_ENGINES + ("ollama",)
    llm.FREE_ENGINES = llm.FREE_ENGINES + ("ollama",)  # fewer requests at once on a laptop
    os.environ.setdefault("OLLAMA_API_KEY", "ollama")  # Ollama ignores the key, but the client expects one
    original_post = llm._post

    def slow_post(url, headers, payload, timeout=60, retries=2):  # local models on a laptop can be slow
        return original_post(url, headers, payload, timeout=600, retries=1)
    llm._post = slow_post


def fmt(v):
    return "n/a" if v is None else f"{v:.0%}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=os.getenv("RESULTWISE_LOCAL_MODEL", "qwen2.5:7b"))
    ap.add_argument("--all", action="store_true", help="also run the 104 development reports")
    args = ap.parse_args()

    check_ollama(args.model)
    register_local_model(args.model)
    print(f"Local model: {args.model} via Ollama at {OLLAMA}. No text leaves this computer.\n")

    results = {"model": args.model}
    for name in (["heldout", "development"] if args.all else ["heldout"]):
        reports = load_set(name)
        t0 = time.time()
        m = evaluate(reports, "ollama",
                     progress=lambda n, total: print(f"  {name}: {n}/{total} reports", end="\r", flush=True))
        secs = time.time() - t0
        results[name] = {**m, "seconds": round(secs, 1)}
        print(f"\n== {name} set: {m['n_reports']} reports, {m['gold_items']} labelled follow-ups, "
              f"{secs:.0f}s ({secs / m['n_reports']:.1f}s per report)")
        if name == "heldout":
            cols = [f"Local ({args.model})", *REFERENCE]
            print(f"\n  {'':28s}" + "".join(f"{c:>26s}" for c in cols))
            for k, label in LABELS.items():
                vals = [m[k], *(REFERENCE[c][k] for c in REFERENCE)]
                print(f"  {label:28s}" + "".join(f"{fmt(v):>26s}" for v in vals))
        else:
            for k, label in LABELS.items():
                print(f"  {label:28s}{fmt(m[k]):>8s}")
        fallbacks = sum(1 for r in m["rows"] if "fallback" in str(r.get("engine", "")))
        if fallbacks:
            print(f"  Note: {fallbacks} report(s) fell back to the keyword rules because the model's answer "
                  "was unreadable or failed the format check (these count against the local model).")
        for row in m["rows"]:
            if row["errors"] != "-":
                print(f"  {row['report']}: {row['errors']}")

    out = Path(__file__).with_name("local_eval_results.json")
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved to {out.name}. Small synthetic test set: not clinical validation.")


if __name__ == "__main__":
    main()
