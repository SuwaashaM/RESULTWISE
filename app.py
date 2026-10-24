"""Resultwise: follow-up safety net (Streamlit MVP).

Run:  streamlit run app.py
AI: set ANTHROPIC_API_KEY (environment or Streamlit secrets) and Claude reads reports, translates and writes
easy-read messages. Without a key it falls back to transparent offline rules.
All data is synthetic. Not a medical device; a hackathon prototype.
"""
import json
import os
from datetime import date

import streamlit as st

# Streamlit Cloud: copy secrets into the environment before the AI client reads them
try:
    for _k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "RESULTWISE_CLAUDE_MODEL", "RESULTWISE_CLAUDE_FAST_MODEL",
               "RESULTWISE_OPENAI_MODEL"):
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:  # no secrets file: offline mode
    pass

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from resultwise import db, fhir, llm, messages, pipeline, rules, ui  # noqa: E402
from resultwise.evaluate import evaluate, load_set  # noqa: E402
from resultwise.schema import PLAIN_TEST_NAME  # noqa: E402

st.set_page_config(page_title="Resultwise", layout="wide")
st.markdown(ui.CSS + ui.PORTAL_CSS, unsafe_allow_html=True)

STATUS_LABEL = {
    "open": "Open", "due_soon": "Due soon, not booked", "booked": "Booked", "completed": "Loop closed",
    "overdue": "Overdue", "dismissed": "Dismissed",
}
TEST_LABEL = {k: v[0].upper() + v[1:] for k, v in PLAIN_TEST_NAME.items()}
DISMISS_REASONS = ["Not clinically indicated", "Already done elsewhere", "Patient declined (documented)",
                   "AI extraction error", "Duplicate task", "Other"]
TRUSTS = ("Northbridge Hospitals", "Valeford Hospitals")
ENGINES = {"Claude (AI)": "claude", "OpenAI (AI)": "openai", "Offline rules (no AI)": "offline"}


@st.cache_resource
def get_conn():
    c = db.connect()
    pipeline.ensure_db(c)
    return c


conn = get_conn()
pipeline.ensure_db(conn)  # rebuilds the demo if the database was created by an older version of the app


def q(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def html(s):
    st.markdown(s, unsafe_allow_html=True)


if "engine_label" not in st.session_state:
    st.session_state["engine_label"] = {"claude": "Claude (AI)", "openai": "OpenAI (AI)"}.get(
        llm.default_engine(), "Offline rules (no AI)")

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    html('<div class="rw-brand"><span class="ring"></span>Resultwise</div>')
    st.caption("No follow-up silently lost")
    role = st.radio("I am", ["Clinician", "Patient"], horizontal=True, key="role")
    engine_label = st.session_state["engine_label"]
    engine = ENGINES[engine_label]
    key = st.session_state.get("api_key") or None
    inject = st.session_state.get("inject", False)
    ai_ready = engine != "offline" and bool(llm.available_key(engine, key))

    today = db.today(conn)
    st.caption("Simulated date")
    html(f'<div class="rw-date">{date.fromisoformat(today).strftime("%a %d %b %Y")}</div>')
    if role == "Clinician":
        st.caption("Move time forward")
        c1, c2, c3 = st.columns(3)
        for col, (lbl, days) in zip((c1, c2, c3), (("+1 wk", 7), ("+2 wk", 14), ("+4 wk", 28))):
            if col.button(lbl, width="stretch"):
                rules.advance(conn, days, engine, key, inject)
                st.rerun()
        page = st.radio("View", ["Worklist", "Review and approve", "Report inbox", "Patient journey", "Equity",
                                 "Evaluation", "Audit log"], label_visibility="collapsed")
    else:
        page = "Patient portal"

    with st.expander("Settings"):
        st.selectbox("AI engine", list(ENGINES), key="engine_label")
        if engine != "offline":
            st.text_input("API key (optional if set as a secret)", type="password", key="api_key")
        st.toggle("Simulate a translation error", key="inject",
                  help="Changes the date in new translations, to show the safety check blocking it.")
        if st.button("Reset demo", width="stretch"):
            pipeline.reset_demo(conn)
            for k in list(st.session_state):
                if k not in ("engine_label", "api_key", "role"):
                    del st.session_state[k]
            st.rerun()
    status_txt = (f"AI on: {llm.CLAUDE_MODEL if engine == 'claude' else llm.OPENAI_MODEL}" if ai_ready
                  else "AI off: offline rules" if engine == "offline" else "AI key missing: offline fallback")
    st.caption(status_txt)
    st.caption("All patients, hospitals and phone numbers are invented.")


def tasks_df():
    df = q("""SELECT t.*, p.name, p.age, p.language, p.channel, p.nhs_number, r.source_trust, r.text AS report_text,
                     r.modality, r.report_date, r.engine AS read_by
              FROM tasks t JOIN patients p ON p.id=t.patient_id JOIN reports r ON r.id=t.report_id""")
    if df.empty:
        return df
    df["days_left"] = (pd.to_datetime(df["due_date"]) - pd.Timestamp(db.today(conn))).dt.days

    def prio(r):
        if r.status in ("completed", "dismissed"):
            return 9
        if r.requires_call and not r.patient_called:
            return 0
        if r.status == "overdue":
            return 1 if r.escalation_level >= 2 else 2
        if r.review_state == "needs_review":
            return 3
        return {"due_soon": 4, "open": 5, "booked": 6}.get(r.status, 7)
    df["priority"] = df.apply(prio, axis=1)
    return df.sort_values(["priority", "due_date"])


def status_text(r):
    s = STATUS_LABEL[r["status"]]
    if r["status"] == "overdue":
        s += ", nurse outreach" if r["escalation_level"] >= 2 else ", clinician alerted"
    return s


def view_state(txt: str) -> str:
    if "OVERDUE" in txt:
        return "overdue"
    if "No record" in txt or "not tracked" in txt:
        return "due_soon"
    if txt == "Done":
        return "completed"
    if txt.startswith("Booked"):
        return "booked"
    return "open"


def nz(v, default=""):
    return default if v is None or (isinstance(v, float) and pd.isna(v)) else v


# ============================================================================= patient portal
if page == "Patient portal":
    sent = q("""SELECT m.*, p.name, p.language AS pref_lang, t.responsible_trust, t.test, t.due_date, t.id AS tid,
                       p.id AS pid FROM messages m JOIN patients p ON p.id=m.patient_id JOIN tasks t ON t.id=m.task_id
                WHERE m.status='sent' ORDER BY m.id DESC""")
    if sent.empty:
        html('<div class="rw-hint">No patient has a message yet. As a <b>Clinician</b>: click <b>+2 wk</b>, then '
             'approve a message on the Worklist. Then come back here as the <b>Patient</b>.</div>')
        st.stop()
    people = {f"{r['name']} (NHS {nz(conn.execute('SELECT nhs_number FROM patients WHERE id=?', (r['pid'],)).fetchone()[0])})": r["pid"]
              for _, r in sent.iterrows()}
    pid = people[st.selectbox("Signed in as (demo)", list(people))]
    mine = sent[sent.pid == pid]
    first = mine.iloc[0]
    html(f'<div class="rw-portal"><div class="hello">Hello {ui.esc(first["name"].split()[0])}</div>'
         f'<div class="sub">You have {len(mine)} message{"s" if len(mine) > 1 else ""} from your care team.</div></div>')

    # accessibility toolbar
    langs = list(messages.LANGUAGES)
    default_lang = first["pref_lang"] if first["pref_lang"] in langs else "English"
    t1, t2, t3, t4 = st.columns([3, 2, 2, 2])
    lang = t1.selectbox("Language", langs, index=langs.index(default_lang), key=f"lang_{pid}")
    size_lbl = t2.select_slider("Text size", ["Standard", "Large", "Extra large"], key=f"size_{pid}")
    hc = t3.toggle("High contrast", key=f"hc_{pid}")
    easy = t4.toggle("Easy read", key=f"easy_{pid}")
    size = {"Standard": 1.05, "Large": 1.35, "Extra large": 1.7}[size_lbl]

    for _, m in mine.iterrows():
        p = dict(conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone())
        task = dict(conn.execute("SELECT * FROM tasks WHERE id=?", (int(m["tid"]),)).fetchone())
        phone_no = rules.TRUST_PHONE.get(task["responsible_trust"], p["phone"])
        _en, facts = messages.draft_english(p, task, phone_no)
        cache_key = f"pt_{m['id']}_{lang}_{easy}_{engine}"
        note = ""
        if cache_key not in st.session_state:
            if easy:
                text = messages.easy_read(facts, lang, engine, key)
                if lang != "English" and not ai_ready:
                    note = "Easy read in other languages needs the AI engine. Showing English easy read."
            elif lang == "English":
                text = m["text_en"]
            elif lang == m["language"] and nz(m["text_translated"]) and m["text_translated"] != m["text_en"]:
                text = m["text_translated"]  # the version the clinician approved
            else:
                with st.spinner(f"Translating into {lang}..."):
                    text, _back = messages.translate(m["text_en"], facts, task["test"], lang, engine, key)
                ok, notes = messages.fact_check(m["text_en"], text, facts)
                note = ("Translated on request. Dates and phone numbers checked." if ok and text != m["text_en"]
                        else f"No {lang} translation available offline; showing English." if text == m["text_en"]
                        else "Translation check found a problem, so English is shown instead: " + " ".join(notes))
                if not ok:
                    text = m["text_en"]
            st.session_state[cache_key] = (text, note)
        text, note = st.session_state[cache_key]
        html(ui.portal_message(text, lang, f"From your care team at {m['responsible_trust']} · {m['sent_on']}", size, hc,
                               note))
        widget = ui.read_aloud_widget(text, messages.LANGUAGES.get(lang, "en-GB"))
        if hasattr(st, "iframe"):
            st.iframe(widget, height=60)  # message text is passed as escaped JSON data, never as markup
        else:
            components.html(widget, height=60)
        st.markdown("**Reply to your care team**")
        r1, r2, r3, r4 = st.columns(4)
        for col, (kind, label) in zip((r1, r2, r3, r4), (("booked", "I've already booked it"),
                                                          ("call_me", "Please call me"),
                                                          ("cannot_attend", "I can't make it"),
                                                          ("confused", "I don't understand"))):
            if col.button(label, key=f"rp_{kind}_{m['id']}", width="stretch"):
                pipeline.patient_reply(conn, int(m["tid"]), pid, kind, f"Read in {lang}{', easy read' if easy else ''}")
                st.success("Thank you. Your care team has been told and will contact you if needed.")
        st.divider()
    st.caption("This page shows only your own messages. It never shows test results or diagnoses. "
               "If you feel unwell, contact your GP or call 111.")
    st.stop()


# ============================================================================= clinician pages
if page == "Worklist":
    df = tasks_df()
    html(ui.header("Today's follow-ups",
                   "Every recommendation from every scan report, tracked until it happens."))
    html(ui.flow_strip())
    counts = df.status.value_counts().to_dict() if not df.empty else {}
    html(ui.loop_strip(counts))

    live = df[~df.status.isin(["completed", "dismissed"])] if not df.empty else df
    action = live[live.priority <= 4] if not live.empty else live
    n_msgs = conn.execute("SELECT COUNT(*) FROM messages WHERE status IN ('pending_approval','blocked')").fetchone()[0]
    n_review = int((live.review_state == "needs_review").sum()) if not live.empty else 0
    n_calls = int(((live.requires_call == 1) & (live.patient_called == 0)).sum()) if not live.empty else 0
    n_replies = conn.execute("SELECT COUNT(*) FROM replies WHERE status='open'").fetchone()[0]

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader(f"Needs action ({len(action)})")
        if action.empty:
            st.write("Nothing needs action today.")
        for _, r in action.head(10).iterrows():
            html(ui.task_card(r["name"], TEST_LABEL[r.test], r.due_date, int(r.days_left), r.status, status_text(r),
                              r.responsible_trust, bool(r.requires_call and not r.patient_called),
                              r.review_state == "needs_review"))
        if len(action) > 10:
            st.caption(f"and {len(action) - 10} more in Review and approve.")
    with right:
        st.subheader("Waiting for you")
        html(ui.todo_list([("Patients to phone (urgent findings)", n_calls, "overdue"),
                           ("AI results to check", n_review, "due_soon"),
                           ("Patient messages to approve", n_msgs, "booked"),
                           ("Patient replies", n_replies, "open")]))
        st.caption("Open **Review and approve** in the sidebar to work through these one patient at a time.")
        if not df.empty:
            export = df[["id", "name", "nhs_number", "test", "due_date", "status", "urgency", "review_state",
                         "responsible_trust", "confidence", "evidence"]]
            st.download_button("Download worklist (CSV)", export.to_csv(index=False), "resultwise_worklist.csv",
                               "text/csv", width="stretch")

elif page == "Review and approve":
    html(ui.header("Review and approve",
                   "One patient at a time: check what the AI read, correct it, then check and approve the message."))
    replies = q("""SELECT r.*, p.name, t.test FROM replies r JOIN patients p ON p.id=r.patient_id
                   JOIN tasks t ON t.id=r.task_id WHERE r.status='open' ORDER BY r.id""")
    if len(replies):
        with st.expander(f"Patient replies ({len(replies)})", expanded=True):
            for _, r in replies.iterrows():
                html(f'<div class="rw-reply"><b>{ui.esc(r["name"])}</b> · {ui.esc(TEST_LABEL[r["test"]])}<br>'
                     f'{ui.esc(pipeline.REPLY_KINDS[r["kind"]])} ({ui.esc(r["created_on"])}) · {ui.esc(r["note"])}</div>')
                a1, a2, _ = st.columns([2, 2, 4])
                if a1.button("Called the patient", key=f"rc{r['id']}"):
                    pipeline.resolve_reply(conn, int(r["id"]), "Clinician phoned the patient")
                    st.rerun()
                if a2.button("Checked and resolved", key=f"rr{r['id']}"):
                    pipeline.resolve_reply(conn, int(r["id"]), "Checked and resolved")
                    st.rerun()

    df = tasks_df()
    if df.empty:
        st.info("No follow-ups yet. Read reports in the Report inbox.")
        st.stop()
    pending_msg = set(q("SELECT task_id FROM messages WHERE status IN ('pending_approval','blocked')").task_id)
    show_all = st.toggle("Show all follow-ups (not just ones needing attention)", value=False)
    queue = df if show_all else df[(df.priority <= 4) | df.id.isin(pending_msg)]
    queue = queue[~queue.status.isin(["completed", "dismissed"])] if not show_all else queue
    if queue.empty:
        st.success("Nothing waiting. Turn on 'Show all follow-ups' to look at any patient.")
        st.stop()

    def tag(r):
        bits = []
        if r.requires_call and not r.patient_called:
            bits.append("phone patient")
        if r.review_state == "needs_review":
            bits.append("check AI")
        if r.id in pending_msg:
            bits.append("message to approve")
        return f"{r['name']} · {TEST_LABEL[r.test]} · {status_text(r)}" + (f"  [{', '.join(bits)}]" if bits else "")

    labels = {int(r.id): tag(r) for _, r in queue.iterrows()}
    if st.session_state.get("review_tid") not in labels:
        st.session_state.pop("review_tid", None)
    tid = st.selectbox(f"Patient ({len(labels)} in this list)", list(labels), format_func=lambda i: labels[i],
                       key="review_tid")
    t = df[df.id == tid].iloc[0]
    trow = dict(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
    p = dict(conn.execute("SELECT * FROM patients WHERE id=?", (t.patient_id,)).fetchone())
    rep = dict(conn.execute("SELECT * FROM reports WHERE id=?", (t.report_id,)).fetchone())
    sent = conn.execute("SELECT * FROM messages WHERE task_id=? AND status='sent' ORDER BY id DESC", (tid,)).fetchone()
    confirmed = trow["review_state"] == "confirmed"
    html(ui.stepper([
        ("AI read the report", True),
        ("Clinician checked the follow-up", confirmed or trow["status"] == "dismissed"),
        ("Phone call made" if trow["requires_call"] else "Patient message approved",
         bool(trow["patient_called"]) if trow["requires_call"] else sent is not None),
        ("Loop closed: test done", trow["status"] == "completed"),
    ]))
    html(ui.task_card(t["name"], TEST_LABEL[t.test], t.due_date, int(t.days_left), t.status, status_text(t),
                      t.responsible_trust, bool(t.requires_call and not t.patient_called),
                      t.review_state == "needs_review"))

    # ---------------- step 1: compare the report with what the AI extracted
    st.subheader("1. Check what the AI found")
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.markdown(f"**The report** · read by {nz(rep['engine'], 'offline')} · the sentence it used is highlighted")
        html(ui.report_html(rep["text"], trow["evidence"]))
    with c2:
        tab1, tab2 = st.tabs(["Plain English", "FHIR Task (JSON)"])
        with tab1:
            html(ui.plain_summary(p["name"], TEST_LABEL[trow["test"]], trow["due_date"], trow["urgency"],
                                  trow["responsible_trust"], trow["confidence"], trow["evidence"],
                                  trow["review_state"]))
        with tab2:
            fjson = json.dumps(fhir.task_resource(trow, p, rep), indent=2)
            st.code(fjson, language="json")
            st.download_button("Download FHIR Task", fjson, f"resultwise_task_{tid}.json", "application/json")
        if trow["status"] not in ("completed", "dismissed"):
            with st.form(f"edit{tid}", border=True):
                st.markdown("**Correct anything that's wrong, then confirm**")
                tests = list(PLAIN_TEST_NAME)
                f1, f2, f3 = st.columns([2.2, 1.4, 1.2])
                new_test = f1.selectbox("Test", tests, index=tests.index(trow["test"]),
                                        format_func=lambda k: TEST_LABEL[k])
                new_due = f2.date_input("Due by", value=date.fromisoformat(trow["due_date"]))
                new_urg = f3.selectbox("Urgency", ["routine", "soon", "urgent"],
                                       index=["routine", "soon", "urgent"].index(trow["urgency"]))
                if st.form_submit_button("Confirm follow-up", type="primary"):
                    if (new_test, new_due.isoformat(), new_urg) == (trow["test"], trow["due_date"], trow["urgency"]):
                        pipeline.confirm_task(conn, tid)
                    else:
                        pipeline.edit_task(conn, tid, new_due.isoformat(), new_urg, test=new_test)
                    st.rerun()
            with st.expander("Not needed? Dismiss with a reason"):
                reason = st.selectbox("Reason", DISMISS_REASONS, key=f"rs{tid}")
                note = st.text_input("Note", key=f"nt{tid}")
                if st.button("Dismiss follow-up", key=f"ds{tid}"):
                    pipeline.dismiss_task(conn, tid, reason + (f": {note}" if note else ""))
                    st.rerun()

    # ---------------- step 2: message (or phone call for urgent findings)
    st.subheader("2. Phone the patient" if trow["requires_call"] else "2. Check and approve the patient message")
    if trow["status"] == "dismissed":
        st.write("Dismissed. No message will be sent.")
    elif trow["requires_call"]:
        st.error("Urgent finding: a clinician phones the patient. Resultwise never sends an automated message for this.")
        st.write(f"Phone {p['name']} on the number in their record. Preferred language: {p['language']}"
                 + (" (book an interpreter)." if p["language"] != "English" else "."))
        if not trow["patient_called"] and st.button("Mark patient phoned", type="primary"):
            pipeline.mark_called(conn, tid)
            st.rerun()
    elif sent is not None:
        st.success(f"Sent on {sent['sent_on']} by {sent['approved_by']} ({sent['language']}, via {sent['channel']}).")
        html(ui.message_card(p["name"], TEST_LABEL[trow["test"]], sent["language"], sent["channel"], sent["text_en"],
                             sent["text_translated"], nz(sent["back_translation"]), bool(sent["check_passed"]),
                             nz(sent["check_notes"])))
    else:
        draft = conn.execute("SELECT * FROM messages WHERE task_id=? AND status IN ('pending_approval','blocked') "
                             "ORDER BY id DESC", (tid,)).fetchone()
        phone_no = rules.TRUST_PHONE.get(trow["responsible_trust"], p["phone"])
        default_en, facts = messages.draft_english(p, trow, phone_no)
        if draft is None:
            st.caption("No message drafted yet (one is drafted automatically when a follow-up goes overdue). "
                       "You can write and send a reminder now.")
        lang = p["language"]
        m1, m2 = st.columns(2, gap="large")
        with m1:
            st.markdown("**English: what you approve** (edit freely; keep the date and phone number)")
            en = st.text_area("English message", draft["text_en"] if draft else default_en, height=210,
                              key=f"en{tid}", label_visibility="collapsed")
        with m2:
            st.markdown(f"**{lang}: what {p['name'].split()[0]} reads**" if lang != "English"
                        else "**No translation needed** (patient prefers English)")
            ck = f"tr{tid}"
            if lang != "English":
                stored = (draft is not None and draft["text_en"] == en and draft["text_translated"])
                if ck not in st.session_state and stored:
                    st.session_state[ck] = (en, draft["text_translated"], nz(draft["back_translation"]))
                if st.button(f"Translate into {lang} and check", key=f"tb{tid}"):
                    if not ai_ready and en.strip() != default_en.strip():
                        tr, back = en, ""  # offline templates can't translate edited wording
                    else:
                        with st.spinner("Translating and back-translating..."):
                            tr, back = messages.translate(en, facts, trow["test"], lang, engine, key, inject)
                    st.session_state[ck] = (en, tr, back)
                cached = st.session_state.get(ck)
                if cached and cached[0] == en:
                    _, tr, back = cached
                    if tr == en:
                        st.warning(f"No {lang} translation available offline for this wording. Add an API key "
                                   "(Settings) to translate any text, or send it in English.")
                        ok, notes = True, []
                    else:
                        ok, notes = messages.fact_check(en, tr, facts)
                        html(f'<div class="rw-msg"><div class="text" dir="{ui.text_dir(lang)}">{ui.esc(tr)}</div>'
                             + (f'<div class="label" style="margin-top:.6rem">Back into English: {ui.esc(back)}</div>'
                                if back else "") + "</div>")
                        (st.success if ok else st.error)(
                            "Check passed: date, phone number and name are unchanged." if ok
                            else "Blocked: " + " ".join(notes))
                else:
                    tr, back, ok, notes = None, "", False, ["Translation not checked for this English text yet."]
                    st.info("Click the button to translate this English text and run the safety check. "
                            "If you edit the English, check again.")
            else:
                tr, back, ok, notes = None, "", True, []
                st.info("The English message on the left is exactly what the patient receives.")
        ready = confirmed and ok
        why = ("Confirm the follow-up in step 1 first." if not confirmed
               else "Translate and pass the safety check first." if not ok else "")
        a1, a2 = st.columns([2, 5])
        if a1.button("Approve and send", type="primary", disabled=not ready, key=f"send{tid}"):
            pipeline.send_message(conn, tid, en, tr if tr != en else None, back, ok, notes,
                                  edited=(en != (draft["text_en"] if draft else default_en)))
            st.session_state.pop(ck, None)
            st.rerun()
        if why:
            a2.caption(why)

elif page == "Patient journey":
    html(ui.header("One patient, two hospitals",
                   "Each hospital's own record only sees its own bookings. Resultwise follows the patient across both."))
    pts = q("SELECT DISTINCT p.id, p.name FROM patients p JOIN tasks t ON t.patient_id=p.id ORDER BY p.id")
    labels = {f"{r['name']} ({r['id']})": r["id"] for _, r in pts.iterrows()}
    default = next((i for i, k in enumerate(labels) if "P001" in k), 0)
    pid = labels[st.selectbox("Patient", list(labels), index=default)]
    p = conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    st.markdown(f"**{p['name']}**, {p['age']}, NHS number {p['nhs_number']} (test range). Prefers {p['language']}, "
                f"contact by {p['channel']}. Registered at {p['home_trust']}.")
    for t in conn.execute("SELECT * FROM tasks WHERE patient_id=? ORDER BY due_date", (pid,)).fetchall():
        rep = conn.execute("SELECT * FROM reports WHERE id=?", (t["report_id"],)).fetchone()
        views = rules.trust_views(conn, t)
        why = (f"Recommended in a {rep['modality'].lower()} report at {rep['source_trust']} on {rep['report_date']}, "
               f"to be done at {rep['follow_up_trust']} by {t['due_date']}.")
        html(ui.lanes(TEST_LABEL[t["test"]], why,
                      [(tr, "own record only", view_state(views[tr]), views[tr]) for tr in TRUSTS]
                      + [("Resultwise", "every trust", t["status"], status_text(t))]))
    audit = q("""SELECT a.sim_date AS date, a.actor AS who, a.action AS event, a.detail FROM audit a
                 JOIN tasks t ON t.id=a.task_id WHERE t.patient_id=? ORDER BY a.id""", (pid,))
    st.subheader("What happened, in order")
    st.dataframe(audit, hide_index=True, width="stretch")

elif page == "Report inbox":
    html(ui.header("Report inbox", "New reports are read by the AI and turned into follow-up tasks. "
                   "Every output is checked before it reaches a clinician.", tag=status_txt))
    n_all = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    by_engine = q("SELECT COALESCE(engine,'not yet read') AS engine, COUNT(*) AS reports FROM reports GROUP BY 1")
    st.caption("Reports read so far: " + ", ".join(f"{r.reports} by {r.engine}" for r in by_engine.itertuples()))
    if engine != "offline":
        if st.button(f"Re-read all {n_all} reports with {engine_label}", disabled=not ai_ready):
            bar = st.progress(0.0, text="Reading reports...")
            pipeline.reprocess_all(conn, engine, key,
                                   progress=lambda d, n: bar.progress(d / n, text=f"Read {d} of {n} reports"))
            st.rerun()
        if not ai_ready:
            st.caption("Add an API key (Settings, or Streamlit secrets) to enable this.")
    new = q("SELECT id, patient_id, report_date, modality, text FROM reports WHERE processed=0 ORDER BY report_date")
    if new.empty:
        st.success("No new reports waiting.")
    else:
        if st.button(f"Read all {len(new)} new reports", type="primary"):
            with st.spinner("Reading reports..."):
                for rid in new.id:
                    pipeline.process_report(conn, rid, engine, key)
            st.rerun()
        for _, r in new.iterrows():
            with st.expander(f"{r.modality} · {r.report_date} · patient {r.patient_id}"):
                html(ui.report_html(r.text, None))
                if st.button("Read this report", key=f"pr{r.id}"):
                    with st.spinner("Reading..."):
                        res, created = pipeline.process_report(conn, r.id, engine, key)
                    st.session_state["last_result"] = (r.id, res.extraction.model_dump(), res.issues, res.engine_used)
                    st.rerun()
    if "last_result" in st.session_state:
        rid, ex, issues, used = st.session_state["last_result"]
        st.subheader(f"What the AI extracted from {rid} ({used})")
        st.json(ex)
        for i in issues:
            st.warning(i)

    st.subheader("Try your own report")
    pts = q("SELECT id, name FROM patients ORDER BY id")
    pmap = {f"{r['name']} ({r['id']})": r["id"] for _, r in pts.iterrows()}
    c1, c2 = st.columns(2)
    pid = pmap[c1.selectbox("Patient", list(pmap), key="paste_patient")]
    modality = c2.text_input("Type of report", "Echocardiogram")
    example = ("Echocardiogram.\nFindings: LVEF 52%, down from 60%. GLS -16%.\n"
               "Conclusion: Borderline fall in function. Would suggest a further scan in about a month, and "
               "cardio-oncology input if it drops again.")
    text = st.text_area("Report text (synthetic only, never real patient data)", example, height=140)
    if st.button("Extract follow-ups", type="primary"):
        with st.spinner("Reading..."):
            rid, res, created = pipeline.add_pasted_report(conn, pid, text, modality, engine, key)
        st.success(f"Report {rid}: {len(created)} task(s) created ({res.engine_used}).")
        st.json(res.extraction.model_dump())
        for i in res.issues:
            st.warning(i)

elif page == "Equity":
    html(ui.header("Who is the system failing to reach?",
                   "On-time follow-up across 900 past synthetic follow-ups. The dashed line is the overall rate.",
                   tag="Synthetic, with a built-in disparity"))
    hist = pd.read_csv(pipeline.DATA / "history.csv")
    overall = hist.completed_on_time.mean()

    def bar(frame, col, title, order=None, value="completed_on_time"):
        g = frame.groupby(col).agg(rate=(value, "mean"), n=(value, "size")).reset_index()
        g[col] = g[col].astype(str)
        ref = frame[value].mean()
        g["below"] = g.rate < ref - 0.03
        base = alt.Chart(g).encode(
            y=alt.Y(f"{col}:N", sort=order, title=None),
            x=alt.X("rate:Q", title=None, axis=alt.Axis(format="%", grid=False), scale=alt.Scale(domain=[0, 1])),
            tooltip=[alt.Tooltip(f"{col}:N", title=title), alt.Tooltip("rate:Q", format=".0%", title="Rate"),
                     alt.Tooltip("n:Q", title="Follow-ups")])
        bars = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
            color=alt.condition("datum.below", alt.value(ui.RED), alt.value(ui.TEAL)))
        labels = base.mark_text(align="left", dx=5, color=ui.MUTED).encode(text=alt.Text("rate:Q", format=".0%"))
        rule = alt.Chart(pd.DataFrame({"x": [ref]})).mark_rule(strokeDash=[4, 3], color=ui.INK).encode(x="x:Q")
        return (bars + labels + rule).properties(title=title, height=alt.Step(30)).configure_view(stroke=None)

    st.markdown(f"**{overall:.0%}** of past follow-ups were completed on time. Groups in red are well below that.")
    c1, c2, c3 = st.columns(3)
    c1.altair_chart(bar(hist, "age_band", "Age", ["<50", "50-64", "65-79", "80+"]), width="stretch")
    c2.altair_chart(bar(hist, "language", "Preferred language"), width="stretch")
    h2 = hist.copy()
    h2["imd_quintile"] = h2.imd_quintile.map(lambda v: f"{v}{' (most deprived)' if v == 1 else ''}")
    c3.altair_chart(bar(h2, "imd_quintile", "Deprivation quintile"), width="stretch")

    st.subheader("Right now: booked on time, by group")
    live = tasks_df()
    live = live[live.status.isin(["completed", "booked", "overdue"])].copy()
    if not live.empty:
        pts = q("SELECT id AS patient_id, imd_quintile FROM patients")
        live = live.merge(pts, on="patient_id")
        live["ok"] = live.status.isin(["completed", "booked"]).astype(int)
        live["age_band"] = pd.cut(live.age, [0, 49, 64, 79, 200], labels=["<50", "50-64", "65-79", "80+"]).astype(str)
        live["language_group"] = live.language.where(live.language == "English", "Other languages")
        d1, d2 = st.columns(2)
        d1.altair_chart(bar(live, "age_band", "Age (current tasks)", ["<50", "50-64", "65-79", "80+"], "ok"),
                        width="stretch")
        d2.altair_chart(bar(live, "language_group", "Language (current tasks)", None, "ok"), width="stretch")
        st.caption(f"Based on {len(live)} current follow-ups that are booked, done or overdue. Small numbers: "
                   "treat as a signal to look closer, not a conclusion.")
    html('<div class="rw-hint">What to do with this: change the outreach for the red groups. For example, phone first '
         'for patients over 80, translated letters, and contacting carers. Then measure again.</div>')

elif page == "Evaluation":
    html(ui.header("How accurate is the AI?",
                   "Recall: did it miss a follow-up? That is the safety number. "
                   "Precision: is it raising false alarms?", tag=status_txt))
    a, b = st.columns(2)
    which = a.radio("Report set", ["heldout", "development"], horizontal=True,
                    format_func=lambda s: {"development": "Development (104 reports)",
                                           "heldout": "Held-out (10 unseen reports)"}[s])
    if b.button("Run evaluation", type="primary"):
        with st.spinner("Scoring..."):
            st.session_state["eval"] = evaluate(load_set(which), engine, key)
    if which == "development":
        st.warning("The offline rules were written while looking at these reports, so their score here is optimistic. "
                   "The held-out set is the honest test.")
    m = st.session_state.get("eval")
    if m:
        cols = st.columns(5)
        for col, (lbl, k_) in zip(cols, (("Recall", "recall"), ("Precision", "precision"),
                                         ("Urgent recall", "urgent_recall"), ("Timeframe", "timeframe_accuracy"),
                                         ("Urgency", "urgency_accuracy"))):
            col.metric(lbl, "n/a" if m[k_] is None else f"{m[k_]:.0%}")
        st.caption(f"Engine {m['engine']} · {m['n_reports']} reports · {m['gold_items']} labelled follow-ups · "
                   f"{m['predicted_items']} predicted")
        st.dataframe(pd.DataFrame(m["rows"]), hide_index=True, width="stretch")

elif page == "Audit log":
    html(ui.header("Audit log", "Every AI output, rule decision, patient reply and human action, newest first."))
    st.dataframe(q("SELECT id, sim_date AS date, actor AS who, action AS event, task_id AS task, detail "
                   "FROM audit ORDER BY id DESC"), hide_index=True, width="stretch")
