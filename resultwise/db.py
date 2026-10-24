"""SQLite storage: one file, no server. Holds patients, reports, tasks, bookings, messages and the audit log."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "resultwise.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS patients (
  id TEXT PRIMARY KEY, name TEXT, age INTEGER, sex TEXT, language TEXT, channel TEXT,
  imd_quintile INTEGER, home_trust TEXT, phone TEXT, nhs_number TEXT);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY, patient_id TEXT, report_date TEXT, source_trust TEXT, follow_up_trust TEXT,
  modality TEXT, difficulty TEXT, text TEXT, processed INTEGER DEFAULT 0, engine TEXT, issues TEXT);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, report_id TEXT, patient_id TEXT, finding TEXT, test TEXT,
  due_date TEXT, urgency TEXT, confidence REAL, evidence TEXT, responsible_trust TEXT,
  status TEXT,            -- open | due_soon | booked | completed | overdue | dismissed
  review_state TEXT,      -- auto | needs_review | confirmed | dismissed
  escalation_level INTEGER DEFAULT 0,  -- 0 none, 1 clinician alerted, 2 nurse outreach
  requires_call INTEGER DEFAULT 0, patient_called INTEGER DEFAULT 0,
  created_on TEXT, closed_on TEXT, dismiss_reason TEXT, booking_id INTEGER);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, test TEXT, trust TEXT,
  made_on TEXT, scheduled_for TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, patient_id TEXT, language TEXT, channel TEXT,
  text_en TEXT, text_translated TEXT, back_translation TEXT, check_passed INTEGER, check_notes TEXT,
  status TEXT,            -- pending_approval | blocked | sent | rejected
  created_on TEXT, approved_by TEXT, sent_on TEXT);
CREATE TABLE IF NOT EXISTS replies (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, patient_id TEXT, kind TEXT, note TEXT,
  created_on TEXT, status TEXT DEFAULT 'open', resolved_by TEXT);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sim_date TEXT, actor TEXT, action TEXT, task_id INTEGER, detail TEXT);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (key, str(value)))
    conn.commit()


def today(conn) -> str:
    return get_setting(conn, "today")


def audit(conn, actor: str, action: str, task_id=None, detail: str = ""):
    conn.execute("INSERT INTO audit(sim_date, actor, action, task_id, detail) VALUES(?,?,?,?,?)",
                 (today(conn), actor, action, task_id, detail))
    conn.commit()
