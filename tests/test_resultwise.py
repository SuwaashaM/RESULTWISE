"""Core safety tests. Run: pytest -q"""
import pytest
from pydantic import ValidationError

from resultwise import db, messages, pipeline, rules
from resultwise.evaluate import evaluate, load_set
from resultwise.extract import offline_extract, parse_timeframe, run_extraction
from resultwise.schema import FollowUp


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    pipeline.reset_demo(c)
    yield c
    c.close()


# ---------------------------------------------------------------- extraction

@pytest.mark.parametrize("text,days", [
    ("repeat echo in 12 weeks", 84), ("rpt TTE 6/52", 42), ("Repeat DXA in 12 months", 365),
    ("continue 3-monthly echo surveillance", 90), ("annual mammography", 365), ("within six months", 180),
])
def test_timeframes(text, days):
    assert parse_timeframe(text) == days


def test_negation_creates_no_task():
    assert offline_extract("CT chest.\nConclusion: Stable nodule. No further follow-up is required.").follow_ups == []


def test_non_urgent_is_not_urgent():
    ex = offline_extract("CT neck.\nConclusion: Recommend non-urgent thyroid ultrasound within 3 months.")
    assert ex.follow_ups[0].urgency == "routine"


def test_suspicious_biopsy_is_urgent():
    ex = offline_extract("Mammogram.\nConclusion: R4 - suspicious. Recommend core biopsy.")
    assert ex.follow_ups[0].follow_up_test == "breast_biopsy" and ex.follow_ups[0].urgency == "urgent"


def test_schema_rejects_bad_ai_output():
    with pytest.raises(ValidationError):
        FollowUp(finding="x nodule", follow_up_test="echocardiogram", due_in_days="six weeks",
                 urgency="kinda urgent", evidence="repeat", confidence=0.9)


def test_ai_failure_falls_back_and_flags_review():
    res = run_extraction("Echo.\nConclusion: Repeat echo in 4 weeks.", engine="claude", key=None)
    assert res.engine_used == "offline (fallback)"
    assert res.extraction.follow_ups and all(res.review_flags)


def test_development_set_recall_is_perfect():
    m = evaluate(load_set("development"))
    assert m["recall"] == 1.0 and m["urgent_recall"] == 1.0


# ---------------------------------------------------------------- tracking

def task_for(conn, pid):
    return conn.execute("SELECT * FROM tasks WHERE patient_id=?", (pid,)).fetchone()


def test_cross_trust_gap_is_caught(conn):
    assert task_for(conn, "P001")["status"] == "due_soon"
    rules.advance(conn, 14)
    t = task_for(conn, "P001")
    assert t["status"] == "overdue" and t["escalation_level"] == 1
    views = rules.trust_views(conn, t)
    assert "not tracked" in views["Northbridge Hospitals"]
    assert "No record" in views["Valeford Hospitals"]


def test_booking_at_other_trust_closes_loop(conn):
    rules.advance(conn, 28)
    t = task_for(conn, "P002")
    assert t["status"] == "completed"
    assert "OVERDUE" in rules.trust_views(conn, t)["Northbridge Hospitals"]  # the false alarm a single trust would raise


def test_escalates_to_nurse_after_14_days(conn):
    rules.advance(conn, 28)
    assert task_for(conn, "P001")["escalation_level"] == 2


def test_urgent_tasks_never_get_automated_message(conn):
    for rid in ("R06", "R14", "R23"):
        pipeline.process_report(conn, rid)
    rules.advance(conn, 28)
    urgent_ids = [r["id"] for r in conn.execute("SELECT id FROM tasks WHERE requires_call=1")]
    assert urgent_ids
    assert not conn.execute(f"SELECT 1 FROM messages WHERE task_id IN ({','.join('?' * len(urgent_ids))})",
                            urgent_ids).fetchone()


def test_dismiss_requires_reason_and_is_audited(conn):
    t = task_for(conn, "P001")
    pipeline.dismiss_task(conn, t["id"], "Already done elsewhere")
    row = conn.execute("SELECT * FROM audit WHERE task_id=? AND action LIKE 'Dismissed%'", (t["id"],)).fetchone()
    assert row and "Already done" in row["detail"]


# ---------------------------------------------------------------- messages

def test_message_has_no_diagnosis_and_passes_check(conn):
    rules.advance(conn, 14)
    m = conn.execute("SELECT * FROM messages m JOIN tasks t ON t.id=m.task_id WHERE t.patient_id='P001'").fetchone()
    assert m["status"] == "pending_approval" and m["language"] == "Polish"
    assert "LVEF" not in m["text_en"] and "trastuzumab" not in m["text_en"].lower()


def test_translation_error_is_blocked(conn):
    rules.advance(conn, 14)
    t = task_for(conn, "P001")
    assert rules.draft_message(conn, t, inject_error=True, replace=True) == "blocked"


def test_fact_check_catches_changed_phone():
    p, t = {"name": "Halina Nowak"}, {"due_date": "2026-11-02", "test": "echocardiogram"}
    en, facts = messages.draft_english(p, t, "01632 960 202")
    tr, _ = messages.translate(en, facts, "echocardiogram", "Polish", "offline")
    ok, notes = messages.fact_check(en, tr.replace("960 202", "960 220"), facts)
    assert not ok and any("Phone" in n for n in notes)
