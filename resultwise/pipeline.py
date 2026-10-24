"""Glue: process reports into tasks, clinician actions, and demo reset/seed."""
import csv
import json
from datetime import date, timedelta
from pathlib import Path

from . import db, rules
from .extract import run_extraction

DATA = Path(__file__).resolve().parent.parent / "data"
DEMO_START = "2026-10-25"


def process_report(conn, report_id: str, engine="offline", key=None, actor="system"):
    rep = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    res = run_extraction(rep["text"], engine, key)
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
    rules.run_tracker(conn, engine, key)
    return res, created


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


def edit_task(conn, task_id, due_date, urgency, who="Clinician"):
    conn.execute("UPDATE tasks SET due_date=?, urgency=?, requires_call=?, review_state='confirmed' WHERE id=?",
                 (due_date, urgency, int(urgency == "urgent"), task_id))
    conn.commit()
    db.audit(conn, who, "Corrected and confirmed", task_id, f"due {due_date}, {urgency}")
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


def reject_message(conn, msg_id, who="Clinician"):
    m = conn.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()
    conn.execute("UPDATE messages SET status='rejected' WHERE id=?", (msg_id,))
    conn.commit()
    db.audit(conn, who, "Message rejected", m["task_id"])


# ----------------------------------------------------------------------------- seed / reset

def reset_demo(conn, engine="offline", key=None):
    for t in ("settings", "patients", "reports", "tasks", "bookings", "messages", "audit"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    db.init(conn)
    db.set_setting(conn, "today", DEMO_START)
    with open(DATA / "patients.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            conn.execute("INSERT INTO patients VALUES(?,?,?,?,?,?,?,?,?)",
                         (r["id"], r["name"], int(r["age"]), r["sex"], r["language"], r["channel"],
                          int(r["imd_quintile"]), r["home_trust"], r["phone"]))
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


def ensure_db(conn):
    db.init(conn)
    if db.today(conn) is None:
        reset_demo(conn)
