"""Tracking engine: plain, deterministic rules. No AI in here on purpose.

Every day the tracker looks at each open task and asks one question:
has anyone, at ANY trust, booked this test for this patient?

  booked & date passed        -> completed (loop closed)
  booked, date in future      -> booked
  not booked, due in <=14 d   -> due_soon
  not booked, past due        -> overdue, escalation level 1 (clinician alerted, patient message drafted)
  not booked, 14+ d past due  -> escalation level 2 (nurse outreach)
Urgent tasks never get an automated message: they carry a "phone the patient" flag from day one.
"""
from datetime import date, timedelta

from . import db, messages

DUE_SOON_DAYS = 14
LEVEL2_AFTER_DAYS = 14
TRUST_PHONE = {"Northbridge Hospitals": "01632 960 101", "Valeford Hospitals": "01632 960 202"}


def find_booking(conn, task):
    report_date = conn.execute("SELECT report_date FROM reports WHERE id=?", (task["report_id"],)).fetchone()
    since = report_date["report_date"] if report_date else "1900-01-01"
    return conn.execute(
        "SELECT * FROM bookings WHERE patient_id=? AND test=? AND made_on>=? AND made_on<=? "
        "ORDER BY scheduled_for LIMIT 1",
        (task["patient_id"], task["test"], since, db.today(conn))).fetchone()


def draft_message(conn, task, engine="offline", key=None, inject_error=False, replace=False):
    if task["requires_call"]:
        return None
    if not replace and conn.execute("SELECT 1 FROM messages WHERE task_id=? AND status!='rejected'",
                                    (task["id"],)).fetchone():
        return None
    patient = dict(conn.execute("SELECT * FROM patients WHERE id=?", (task["patient_id"],)).fetchone())
    phone = TRUST_PHONE.get(task["responsible_trust"], patient["phone"])
    text_en, facts = messages.draft_english(patient, dict(task), phone)
    if patient["language"] == "English":
        tr, back, ok, notes = None, "", True, []
    else:
        tr, back = messages.translate(text_en, facts, task["test"], patient["language"], engine, key, inject_error)
        if tr == text_en:  # no translation available (offline, no template): send English, say so
            tr, back, ok, notes = None, "", True, []
        else:
            ok, notes = messages.fact_check(text_en, tr, facts)
    status = "pending_approval" if ok else "blocked"
    if replace:
        conn.execute("UPDATE messages SET status='rejected' WHERE task_id=? AND status IN ('pending_approval','blocked')",
                     (task["id"],))
    conn.execute(
        "INSERT INTO messages(task_id, patient_id, language, channel, text_en, text_translated, back_translation, "
        "check_passed, check_notes, status, created_on) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (task["id"], task["patient_id"], patient["language"], patient["channel"], text_en, tr, back, int(ok),
         "\n".join(notes), status, db.today(conn)))
    conn.commit()
    db.audit(conn, "system", "Patient message drafted" if ok else "Message BLOCKED by translation check",
             task["id"], f"{patient['language']} via {patient['channel']}" + ("" if ok else f": {notes[0]}"))
    return status


def run_tracker(conn, engine="offline", key=None, inject_error=False):
    today = date.fromisoformat(db.today(conn))
    tasks = conn.execute("SELECT * FROM tasks WHERE status NOT IN ('completed','dismissed')").fetchall()
    for t in tasks:
        old_status, old_level = t["status"], t["escalation_level"]
        booking = find_booking(conn, t)
        new_status, level, closed_on, booking_id = old_status, old_level, None, None
        if booking:
            booking_id = booking["id"]
            if date.fromisoformat(booking["scheduled_for"]) <= today:
                new_status, closed_on = "completed", booking["scheduled_for"]
            else:
                new_status = "booked"
        else:
            delta = (date.fromisoformat(t["due_date"]) - today).days
            if delta < 0:
                new_status = "overdue"
                level = 2 if -delta >= LEVEL2_AFTER_DAYS else 1
            elif delta <= DUE_SOON_DAYS:
                new_status = "due_soon"
            else:
                new_status = "open"

        if new_status != old_status or level != old_level:
            conn.execute("UPDATE tasks SET status=?, escalation_level=?, closed_on=?, booking_id=? WHERE id=?",
                         (new_status, max(level, old_level), closed_on, booking_id, t["id"]))
            conn.commit()
            if new_status == "completed":
                db.audit(conn, "system", "Loop closed", t["id"], f"{t['test']} completed at {booking['trust']} on {closed_on}")
            elif new_status == "booked" and old_status != "booked":
                db.audit(conn, "system", "Booking found", t["id"],
                         f"{t['test']} booked at {booking['trust']} for {booking['scheduled_for']}")
            elif new_status == "due_soon" and old_status != "due_soon":
                db.audit(conn, "system", "Due soon, not yet booked", t["id"], f"due {t['due_date']}")
            if level >= 1 and old_level < 1:
                db.audit(conn, "system", "OVERDUE: clinician alerted", t["id"],
                         f"{t['test']} due {t['due_date']}, no booking at any trust")
                draft_message(conn, conn.execute("SELECT * FROM tasks WHERE id=?", (t["id"],)).fetchone(),
                              engine, key, inject_error)
            if level >= 2 and old_level < 2:
                db.audit(conn, "system", "ESCALATED: nurse outreach", t["id"],
                         f"{-(date.fromisoformat(t['due_date']) - today).days} days overdue")


def advance(conn, days: int, engine="offline", key=None, inject_error=False):
    new_day = date.fromisoformat(db.today(conn)) + timedelta(days=days)
    db.set_setting(conn, "today", new_day.isoformat())
    db.audit(conn, "demo", "Clock moved", None, f"+{days} days to {new_day.isoformat()}")
    run_tracker(conn, engine, key, inject_error)


def trust_views(conn, task) -> dict:
    """What each hospital's OWN system would show for this task, versus Resultwise (which sees every trust)."""
    report = conn.execute("SELECT * FROM reports WHERE id=?", (task["report_id"],)).fetchone()
    source, target = report["source_trust"], report["follow_up_trust"]
    today = db.today(conn)
    views = {}
    for trust in ("Northbridge Hospitals", "Valeford Hospitals"):
        b = conn.execute("SELECT * FROM bookings WHERE patient_id=? AND test=? AND trust=? AND made_on>=? AND made_on<=? "
                         "ORDER BY scheduled_for LIMIT 1",
                         (task["patient_id"], task["test"], trust, report["report_date"], today)).fetchone()
        if b:
            views[trust] = "Done" if b["scheduled_for"] <= today else f"Booked for {b['scheduled_for']}"
        elif trust == source and target != source:
            views[trust] = f"Handed over to {target}: not tracked any more"
        elif trust == source:
            views[trust] = "OVERDUE: no booking in our system" if task["due_date"] < today else "Awaiting booking"
        else:
            views[trust] = "No record of this request"
    return views
