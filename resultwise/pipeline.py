"""Glue: process reports into tasks, clinician actions, and demo reset/seed."""
import csv
import json
from datetime import date, timedelta
from pathlib import Path

from . import db, rules
from .extract import run_extraction

DATA = Path(__file__).resolve().parent.parent / "data"
DEMO_START = "2026-10-25"


def process_report(conn, report_id: str, engine="offline", key=None, actor="system", result=None, track=True):
    rep = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    res = result or run_extraction(rep["text"], engine, key)
    conn.execute("DELETE FROM tasks WHERE report_id=? AND review_state IN ('auto','needs_review') "
                 "AND status NOT IN ('completed')", (report_id,))
    created = []
    for fu, needs_review in zip(res.extraction.follow_ups, res.review_flags):
        due = (date.fromisoformat(rep["report_date"]) + timedelta(days=fu.due_in_days)).isoformat()
        cur = conn.execute(
            "INSERT INTO tasks(report_id, patient_id, finding, test, due_date, urgency, confidence, evidence, "
            "responsible_trust, status, review_state, requires_call, created_on) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (report_id, rep["patient_id"], fu.finding, fu.follow_up_test, due, fu.urgency, fu.confidence, fu.evidence,
             rep["follow_up_trust"], "open", "needs_review" if needs_review else "auto",
             int(fu.urgency == "urgent"), db.today(conn)))
        created.append(cur.lastrowid)
        db.audit(conn, f"AI ({res.engine_used})", "Follow-up extracted", cur.lastrowid,
                 f"{fu.follow_up_test} due {due}, {fu.urgency}, confidence {fu.confidence:.2f}"
                 + (" -> needs human review" if needs_review else ""))
        if fu.urgency == "urgent":
            db.audit(conn, "system", "URGENT: clinician to phone patient", cur.lastrowid,
                     "No automated message for urgent findings")
    conn.execute("UPDATE reports SET processed=1, engine=?, issues=? WHERE id=?",
                 (res.engine_used, json.dumps(res.issues), report_id))
    conn.commit()
    if not created:
        db.audit(conn, f"AI ({res.engine_used})", "No follow-up found", None,
                 f"{report_id}: {res.extraction.no_follow_up_reason or ''}")
    for issue in res.issues:
        db.audit(conn, "safety check", "Issue", None, f"{report_id}: {issue}")
    if track:
        rules.run_tracker(conn, engine, key)
    return res, created


def reprocess_all(conn, engine, key=None, workers=None, progress=None):
    """Re-read every report with the chosen engine. AI calls run in parallel; database writes stay in order."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from . import llm
    workers = workers or (2 if engine in llm.FREE_ENGINES else 8)  # free tiers have low rate limits
    reps = conn.execute("SELECT id, text FROM reports ORDER BY id").fetchall()
    results, done = {}, 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_extraction, r["text"], engine, key): r["id"] for r in reps}
        for f in as_completed(futs):
            results[futs[f]] = f.result()
            done += 1
            if progress:
                progress(done, len(reps))
    for rid in sorted(results):
        process_report(conn, rid, engine, key, result=results[rid], track=False)
    rules.run_tracker(conn, engine, key)
    used = {r.engine_used for r in results.values()}
    db.audit(conn, "system", "All reports re-read", None, f"{len(results)} reports, engine(s): {', '.join(sorted(used))}")
    return results


# ----------------------------------------------------------------------------- patient replies

REPLY_KINDS = {"booked": "Patient says it is already booked", "call_me": "Patient asks for a phone call",
               "confused": "Patient does not understand the message", "cannot_attend": "Patient cannot attend"}


def patient_reply(conn, task_id, patient_id, kind, note=""):
    conn.execute("INSERT INTO replies(task_id, patient_id, kind, note, created_on) VALUES(?,?,?,?,?)",
                 (task_id, patient_id, kind, note, db.today(conn)))
    conn.commit()
    db.audit(conn, "patient", REPLY_KINDS[kind], task_id, note)


def resolve_reply(conn, reply_id, outcome, who="Clinician"):
    r = conn.execute("SELECT * FROM replies WHERE id=?", (reply_id,)).fetchone()
    conn.execute("UPDATE replies SET status='resolved', resolved_by=? WHERE id=?", (who, reply_id))
    conn.commit()
    db.audit(conn, who, "Patient reply handled", r["task_id"], outcome)


def add_pasted_report(conn, patient_id, text, modality, engine="offline", key=None):
    n = conn.execute("SELECT COUNT(*) c FROM reports WHERE id LIKE 'N%'").fetchone()["c"] + 1
    rid = f"N{n:02d}"
    p = conn.execute("SELECT home_trust FROM patients WHERE id=?", (patient_id,)).fetchone()
    conn.execute("INSERT INTO reports(id, patient_id, report_date, source_trust, follow_up_trust, modality, difficulty, text)"
                 " VALUES(?,?,?,?,?,?,?,?)",
                 (rid, patient_id, db.today(conn), p["home_trust"], p["home_trust"], modality, "pasted live", text))
    conn.commit()
    return rid, *process_report(conn, rid, engine, key, actor="clinician")


# ----------------------------------------------------------------------------- clinician actions

def confirm_task(conn, task_id, who="Clinician"):
    conn.execute("UPDATE tasks SET review_state='confirmed' WHERE id=?", (task_id,))
    conn.commit()
    db.audit(conn, who, "Confirmed follow-up", task_id)


def edit_task(conn, task_id, due_date, urgency, who="Clinician", test=None):
    old = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    test = test or old["test"]
    conn.execute("UPDATE tasks SET test=?, due_date=?, urgency=?, requires_call=?, review_state='confirmed' WHERE id=?",
                 (test, due_date, urgency, int(urgency == "urgent"), task_id))
    conn.commit()
    changes = [f"{k}: {old[k]} -> {v}" for k, v in (("test", test), ("due_date", due_date), ("urgency", urgency))
               if old[k] != v]
    db.audit(conn, who, "Corrected AI result and confirmed (feedback for model improvement)", task_id, "; ".join(changes))
    rules.run_tracker(conn)


def dismiss_task(conn, task_id, reason, who="Clinician"):
    conn.execute("UPDATE tasks SET status='dismissed', review_state='dismissed', dismiss_reason=?, closed_on=? WHERE id=?",
                 (reason, db.today(conn), task_id))
    conn.execute("UPDATE messages SET status='rejected' WHERE task_id=? AND status IN ('pending_approval','blocked')",
                 (task_id,))
    conn.commit()
    db.audit(conn, who, "Dismissed (feedback for model improvement)", task_id, reason)


def mark_called(conn, task_id, who="Clinician"):
    conn.execute("UPDATE tasks SET patient_called=1 WHERE id=?", (task_id,))
    conn.commit()
    db.audit(conn, who, "Patient phoned", task_id)


def approve_message(conn, msg_id, who="Clinician"):
    m = conn.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()
    conn.execute("UPDATE messages SET status='sent', approved_by=?, sent_on=? WHERE id=?", (who, db.today(conn), msg_id))
    conn.commit()
    db.audit(conn, who, "Message approved and sent", m["task_id"], f"{m['language']} via {m['channel']}")


def send_message(conn, task_id, text_en, text_tr, back, ok, notes, who="Clinician", edited=False):
    """Clinician-approved message: replaces any draft and is sent straight away."""
    p = conn.execute("SELECT p.* FROM patients p JOIN tasks t ON t.patient_id=p.id WHERE t.id=?", (task_id,)).fetchone()
    conn.execute("UPDATE messages SET status='rejected' WHERE task_id=? AND status IN ('pending_approval','blocked')",
                 (task_id,))
    conn.execute(
        "INSERT INTO messages(task_id, patient_id, language, channel, text_en, text_translated, back_translation, "
        "check_passed, check_notes, status, created_on, approved_by, sent_on) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (task_id, p["id"], p["language"], p["channel"], text_en, text_tr, back, int(ok), "\n".join(notes), "sent",
         db.today(conn), who, db.today(conn)))
    conn.commit()
    db.audit(conn, who, "Message " + ("edited, " if edited else "") + "approved and sent", task_id,
             f"{p['language'] if text_tr else 'English'} via {p['channel']}")


def reject_message(conn, msg_id, who="Clinician"):
    m = conn.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()
    conn.execute("UPDATE messages SET status='rejected' WHERE id=?", (msg_id,))
    conn.commit()
    db.audit(conn, who, "Message rejected", m["task_id"])


# ----------------------------------------------------------------------------- seed / reset

def reset_demo(conn, engine="offline", key=None):
    for t in ("settings", "patients", "reports", "tasks", "bookings", "messages", "audit", "replies"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    db.init(conn)
    db.set_setting(conn, "today", DEMO_START)
    db.set_setting(conn, "schema", SCHEMA_VERSION)
    with open(DATA / "patients.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            conn.execute("INSERT INTO patients VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (r["id"], r["name"], int(r["age"]), r["sex"], r["language"], r["channel"],
                          int(r["imd_quintile"]), r["home_trust"], r["phone"], r["nhs_number"]))
    for r in json.loads((DATA / "reports.json").read_text(encoding="utf-8")):
        conn.execute("INSERT INTO reports(id, patient_id, report_date, source_trust, follow_up_trust, modality, "
                     "difficulty, text) VALUES(?,?,?,?,?,?,?,?)",
                     (r["id"], r["patient_id"], r["report_date"], r["source_trust"], r["follow_up_trust"],
                      r["modality"], r["difficulty"], r["text"]))
    with open(DATA / "bookings.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            conn.execute("INSERT INTO bookings(patient_id, test, trust, made_on, scheduled_for) VALUES(?,?,?,?,?)",
                         (r["patient_id"], r["test"], r["trust"], r["made_on"], r["scheduled_for"]))
    conn.commit()
    db.audit(conn, "demo", "Demo reset", None, f"Simulated date {DEMO_START}. All data synthetic.")
    for r in json.loads((DATA / "reports.json").read_text(encoding="utf-8")):
        if r["processed_at_start"]:
            process_report(conn, r["id"], "offline")
    rules.run_tracker(conn, engine, key)


SCHEMA_VERSION = "2"


def ensure_db(conn):
    db.init(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(patients)")}
    if (db.today(conn) is None or db.get_setting(conn, "schema") != SCHEMA_VERSION
            or "nhs_number" not in cols):
        reset_demo(conn)
