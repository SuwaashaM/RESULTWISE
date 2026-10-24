"""Score an extraction engine against gold labels.

Matching: within each report, a predicted follow-up matches a gold one if the test type is the same.
Metrics:
  recall     = matched gold / all gold          (did we miss anything? the safety metric)
  precision  = matched predictions / all predictions   (are we crying wolf?)
  timeframe  = matched items with due_in_days within 10% of gold
  urgency    = matched items with the same urgency
  urgent_recall = gold urgent items found AND labelled urgent (missing these is the worst error)
"""
import json
from pathlib import Path

from .extract import run_extraction

DATA = Path(__file__).resolve().parent.parent / "data"


def load_set(name: str) -> list[dict]:
    fname = {"development": "reports.json", "heldout": "heldout_reports.json"}[name]
    return json.loads((DATA / fname).read_text(encoding="utf-8"))


def evaluate(reports: list[dict], engine: str = "offline", key: str | None = None) -> dict:
    tp = fp = fn = tf_ok = urg_ok = 0
    urgent_gold = urgent_found = 0
    rows = []
    from concurrent.futures import ThreadPoolExecutor
    workers = 8 if engine != "offline" else 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda r: run_extraction(r["text"], engine, key), reports))
    for r, res in zip(reports, results):
        preds = {f.follow_up_test: f for f in res.extraction.follow_ups}
        gold = {g["follow_up_test"]: g for g in r["gold"]}
        errors = []
        for test, g in gold.items():
            if g["urgency"] == "urgent":
                urgent_gold += 1
            p = preds.get(test)
            if p is None:
                fn += 1
                errors.append(f"MISSED {test}")
                continue
            tp += 1
            if abs(p.due_in_days - g["due_in_days"]) <= 0.1 * g["due_in_days"]:
                tf_ok += 1
            else:
                errors.append(f"{test}: due {p.due_in_days}d vs gold {g['due_in_days']}d")
            if p.urgency == g["urgency"]:
                urg_ok += 1
                if g["urgency"] == "urgent":
                    urgent_found += 1
            else:
                errors.append(f"{test}: urgency {p.urgency} vs gold {g['urgency']}")
        for test in preds:
            if test not in gold:
                fp += 1
                errors.append(f"EXTRA {test}")
        rows.append({"report": r["id"], "gold": ", ".join(gold) or "(none)",
                     "predicted": ", ".join(preds) or "(none)", "engine": res.engine_used,
                     "errors": "; ".join(errors) or "-"})
    safe = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    return {
        "engine": engine, "n_reports": len(reports), "gold_items": tp + fn, "predicted_items": tp + fp,
        "recall": safe(tp, tp + fn), "precision": safe(tp, tp + fp),
        "timeframe_accuracy": safe(tf_ok, tp), "urgency_accuracy": safe(urg_ok, tp),
        "urgent_recall": safe(urgent_found, urgent_gold), "rows": rows,
    }
