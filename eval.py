"""Command-line evaluation.

  python eval.py                       # offline engine, both report sets
  python eval.py --engine claude       # needs ANTHROPIC_API_KEY
  python eval.py --engine openai       # needs OPENAI_API_KEY

Writes eval_results.json next to this file.
"""
import argparse
import json
from pathlib import Path

from resultwise.evaluate import evaluate, load_set


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="offline", choices=["offline", "claude", "openai"])
    args = ap.parse_args()
    out = {}
    for name in ("development", "heldout"):
        m = evaluate(load_set(name), args.engine)
        out[name] = m
        print(f"\n== {name} set ({m['n_reports']} reports, {m['gold_items']} labelled follow-ups) engine={args.engine}")
        for k in ("recall", "precision", "urgent_recall", "timeframe_accuracy", "urgency_accuracy"):
            v = m[k]
            print(f"  {k:20s} {'n/a' if v is None else f'{v:.0%}'}")
        for row in m["rows"]:
            if row["errors"] != "-":
                print(f"  {row['report']}: {row['errors']}")
    Path(__file__).with_name("eval_results.json").write_text(json.dumps(out, indent=2))
    print("\nNote: offline rules were tuned on the development set. The held-out set is the honest number.")


if __name__ == "__main__":
    main()
