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


def test_development_set_offline_baseline():
    m = evaluate(load_set("development"))
    assert m["n_reports"] >= 100 and m["recall"] >= 0.95 and m["urgent_recall"] == 1.0 and m["precision"] == 1.0


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


# ---------------------------------------------------------------- AI path (mocked, no network)

def test_claude_output_is_validated_and_evidence_checked(monkeypatch):
    from resultwise import llm
    report = "Echo.\nConclusion: Would suggest a further scan in about a month."
    good = ('{"follow_ups":[{"finding":"borderline LVEF","follow_up_test":"echocardiogram","due_in_days":30,'
            '"urgency":"soon","evidence":"Would suggest a further scan in about a month","confidence":0.8}],'
            '"no_follow_up_reason":null}')
    monkeypatch.setattr(llm, "complete", lambda *a, **k: good)
    res = run_extraction(report, engine="claude", key="test")
    assert res.engine_used == "claude" and res.extraction.follow_ups[0].due_in_days == 30
    assert res.review_flags == [False]
    hallucinated = good.replace("Would suggest a further scan in about a month", "Repeat echo in 4 weeks")
    monkeypatch.setattr(llm, "complete", lambda *a, **k: hallucinated)
    res = run_extraction(report, engine="claude", key="test")
    assert res.review_flags == [True] and any("hallucination" in i for i in res.issues)


def test_claude_bad_json_is_never_dropped(monkeypatch):
    from resultwise import llm
    monkeypatch.setattr(llm, "complete", lambda *a, **k: '{"follow_ups":[{"follow_up_test":"echo"}]}')
    res = run_extraction("Echo.\nConclusion: Repeat echo in 4 weeks.", engine="claude", key="test")
    assert res.engine_used == "offline (fallback)" and res.extraction.follow_ups and all(res.review_flags)


def test_no_temperature_sent_to_claude(monkeypatch):
    from resultwise import llm
    seen = {}

    def fake_post(url, headers, payload, timeout=120):
        seen.update(payload)
        return {"content": [{"type": "text", "text": "ok"}]}
    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.complete("claude", "sys", "hi", key="k") == "ok"
    assert "temperature" not in seen and seen["model"].startswith("claude")


# ---------------------------------------------------------------- MVP features

def test_full_report_format_and_nhs_test_numbers():
    reps = load_set("development")
    r = next(x for x in reps if x["id"] == "R01")
    assert "NHS number: 999" in r["text"] and "Reported by:" in r["text"] and "Clinical indication:" in r["text"]


def test_patient_reply_reaches_clinicians(conn):
    t = task_for(conn, "P001")
    pipeline.patient_reply(conn, t["id"], "P001", "call_me", "Read in Polish")
    assert conn.execute("SELECT COUNT(*) FROM replies WHERE status='open'").fetchone()[0] == 1
    rid = conn.execute("SELECT id FROM replies").fetchone()[0]
    pipeline.resolve_reply(conn, rid, "Phoned")
    assert conn.execute("SELECT status FROM replies").fetchone()[0] == "resolved"


def test_fhir_task_export(conn):
    from resultwise import fhir
    t = dict(task_for(conn, "P001"))
    p = dict(conn.execute("SELECT * FROM patients WHERE id='P001'").fetchone())
    r = dict(conn.execute("SELECT * FROM reports WHERE id=?", (t["report_id"],)).fetchone())
    res = fhir.task_resource(t, p, r)
    assert res["resourceType"] == "Task" and res["for"]["identifier"]["value"].startswith("999")
    assert res["restriction"]["period"]["end"] == t["due_date"]


def test_easy_read_offline_keeps_facts():
    facts = {"first_name": "Halina", "test": "heart scan", "due": "02/11/2026", "phone": "01632 960 202"}
    text = messages.easy_read(facts, "English", "offline")
    assert "02/11/2026" in text and "01632 960 202" in text and len(text.splitlines()) >= 4


@pytest.mark.parametrize("engine,url_part,field", [("gemini", "generativelanguage.googleapis.com", "max_tokens"),
                                                    ("groq", "api.groq.com", "max_completion_tokens")])
def test_free_providers_use_openai_compatible_requests(monkeypatch, engine, url_part, field):
    from resultwise import llm
    seen = {}

    def fake_post(url, headers, payload, timeout=120):
        seen.update(url=url, payload=payload, headers=headers)
        return {"choices": [{"message": {"content": "hello"}}]}
    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.complete(engine, "sys", "hi", key="k") == "hello"
    assert url_part in seen["url"] and seen["url"].endswith("/chat/completions")
    assert field in seen["payload"] and "temperature" not in seen["payload"]
    assert seen["headers"]["authorization"] == "Bearer k"


def test_rate_limit_is_retried(monkeypatch):
    import io
    import urllib.error
    from resultwise import llm
    calls = {"n": 0}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too many", {"retry-after": "0"}, io.BytesIO(b"slow down"))
        return Resp(b'{"choices":[{"message":{"content":"ok"}}]}')
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.complete("groq", "s", "u", key="k") == "ok" and calls["n"] == 2


def test_default_engine_prefers_paid_then_free(monkeypatch):
    from resultwise import llm
    for k in llm.KEY_ENV.values():
        monkeypatch.delenv(k, raising=False)
    assert llm.default_engine() == "offline"
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert llm.default_engine() == "groq"
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert llm.default_engine() == "gemini"


def test_gemini_uses_low_latency_settings(monkeypatch):
    from resultwise import llm
    seen = {}
    monkeypatch.setattr(llm, "_post", lambda url, h, payload, timeout=60: seen.update(payload) or
                        {"choices": [{"message": {"content": "OK"}}]})
    llm.complete("gemini", "s", "u", key="k")
    assert seen["reasoning_effort"] == "low" and seen["model"] == llm.COMPAT["gemini"][2]


def test_source_check_blocks_diagnosis_and_wrong_facts():
    facts = {"first_name": "Halina", "test": "heart scan (echocardiogram)", "due": "02/11/2026", "phone": "01632 960 202"}
    p, t = {"name": "Halina Nowak"}, {"due_date": "2026-11-02", "test": "echocardiogram"}
    en, f = messages.draft_english(p, t, "01632 960 202")
    assert all(ok for _, ok in messages.source_check(en, f))
    bad = en.replace("02/11/2026", "09/11/2026") + " Your LVEF has dropped."
    res = dict(messages.source_check(bad, facts))
    assert not all(res.values())
    assert any("found: lvef" in k for k in res)
