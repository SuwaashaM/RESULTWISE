"""Resultwise: follow-up safety net demo (Streamlit).

Run:  streamlit run app.py
All data is synthetic. Nothing here is a medical device; it is a hackathon prototype.
"""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from resultwise import db, llm, messages, pipeline, rules, ui
from resultwise.evaluate import evaluate, load_set
from resultwise.schema import PLAIN_TEST_NAME

st.set_page_config(page_title="Resultwise", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)

STATUS_LABEL = {
    "open": "Open", "due_soon": "Due soon, not booked", "booked": "Booked", "completed": "Loop closed",
    "overdue": "Overdue", "dismissed": "Dismissed",
}
TEST_LABEL = {k: v[0].upper() + v[1:] for k, v in PLAIN_TEST_NAME.items()}
DISMISS_REASONS = ["Not clinically indicated", "Already done elsewhere", "Patient declined (documented)",
                   "AI extraction error", "Duplicate task", "Other"]
TRUSTS = ("Northbridge Hospitals", "Valeford Hospitals")


@st.cache_resource
def get_conn():
    c = db.connect()
    pipeline.ensure_db(c)
    return c


conn = get_conn()


def q(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def html(s):
    st.markdown(s, unsafe_allow_html=True)


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    html('<div class="rw-brand"><span class="ring"></span>Resultwise</div>')
    st.caption("No follow-up silently lost")
    today = db.today(conn)
    st.caption("Simulated date")
    html(f'<div class="rw-date">{date.fromisoformat(today).strftime("%a %d %b %Y")}</div>')

    st.caption("Move time forward")
    c1, c2, c3 = st.columns(3)
    engine_label = st.session_state.get("engine_label", "Offline (no key needed)")
    engine = {"Offline (no key needed)": "offline", "Claude": "claude", "OpenAI": "openai"}[engine_label]
    key = st.session_state.get("api_key") or None
    inject = st.session_state.get("inject", False)
    for col, (lbl, days) in zip((c1, c2, c3), (("+1 wk", 7), ("+2 wk", 14), ("+4 wk", 28))):
        if col.button(lbl, width="stretch"):
            rules.advance(conn, days, engine, key, inject)
            st.rerun()

    page = st.radio("View", ["Worklist", "Patient journey", "Report inbox", "Patient view", "Equity",
                             "Evaluation", "Audit log"], label_visibility="collapsed")

    with st.expander("Settings"):
        st.selectbox("AI engine", ["Offline (no key needed)", "Claude", "OpenAI"], key="engine_label")
        if engine != "offline":
            st.text_input("API key", type="password", key="api_key",
                          help="Kept in this browser session only. Or set ANTHROPIC_API_KEY / OPENAI_API_KEY.")
            if not llm.available_key(engine, key):
                st.warning("No key: falls back to offline mode and flags tasks for review.")
        st.toggle("Simulate a translation error", key="inject",
                  help="Changes the date in new translations, to show the safety check blocking it.")
        if st.button("Reset demo", width="stretch"):
            pipeline.reset_demo(conn)
            for k in list(st.session_state):
                if k not in ("engine_label", "api_key"):
                    del st.session_state[k]
            st.rerun()
    st.caption("All patients, hospitals and phone numbers are invented.")


def tasks_df():
    df = q("""SELECT t.*, p.name, p.age, p.language, p.channel, r.source_trust, r.text AS report_text,
                     r.modality, r.report_date
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


# ----------------------------------------------------------------------------- pages
if page == "Worklist":
    df = tasks_df()
    html(ui.header("Today's follow-ups",
                   "Every recommendation from every scan report, tracked until it happens. "
                   "Act on the top of the list first."))
    counts = df.status.value_counts().to_dict() if not df.empty else {}
    html(ui.loop_strip(counts))

    msgs = q("""SELECT m.*, p.name, t.test FROM messages m JOIN patients p ON p.id=m.patient_id
                JOIN tasks t ON t.id=m.task_id WHERE m.status IN ('pending_approval','blocked') ORDER BY m.id""")
    live = df[~df.status.isin(["completed", "dismissed"])] if not df.empty else df
    action = live[live.priority <= 4] if not live.empty else live

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader(f"Needs action ({len(action)})")
        if action.empty:
            st.write("Nothing needs action today.")
        for _, r in action.head(8).iterrows():
            html(ui.task_card(r["name"], TEST_LABEL[r.test], r.due_date, int(r.days_left), r.status, status_text(r),
                              r.responsible_trust, bool(r.requires_call and not r.patient_called),
                              r.review_state == "needs_review"))
    with right:
        st.subheader(f"Messages to approve ({len(msgs)})")
        if not (msgs.language != "English").any():
            html('<div class="rw-hint">Translated messages appear when a non-English-speaking patient\'s follow-up '
                 'goes overdue. Click <b>+2 wk</b> to see Polish, Tamil and Urdu messages, or preview any patient\'s '
                 'translation from the task panel below.</div>')
        for _, m in msgs.iterrows():
            tr_text = None if pd.isna(m["text_translated"]) else m["text_translated"]
            back_text = "" if pd.isna(m["back_translation"]) else m["back_translation"]
            html(ui.message_card(m["name"], TEST_LABEL[m["test"]], m["language"], m["channel"], m["text_en"],
                                 tr_text, back_text, bool(m["check_passed"]),
                                 (m["check_notes"] or "").replace("\n", " ")))
            b1, b2, b3 = st.columns([5, 4, 3])
            if b1.button("Approve and send", key=f"ap{m['id']}", disabled=m["status"] == "blocked", type="primary"):
                pipeline.approve_message(conn, m["id"])
                st.rerun()
            if b2.button("Regenerate", key=f"rg{m['id']}"):
                t = conn.execute("SELECT * FROM tasks WHERE id=?", (int(m["task_id"]),)).fetchone()
                rules.draft_message(conn, t, engine, key, inject, replace=True)
                st.rerun()
            if b3.button("Reject", key=f"rj{m['id']}"):
                pipeline.reject_message(conn, m["id"])
                st.rerun()
            st.write("")

    st.divider()
    st.subheader("Open a task")
    if df.empty:
        st.info("No tasks yet. Process reports in the Report inbox.")
    else:
        show_closed = st.toggle("Include closed and dismissed tasks", value=False)
        view = df if show_closed else live
        options = {f"{r['name']} · {TEST_LABEL[r.test]} · {status_text(r)}": int(r.id) for _, r in view.iterrows()}
        choice = st.selectbox("Task", list(options), label_visibility="collapsed")
        t = df[df.id == options[choice]].iloc[0]
        a, b = st.columns([3, 2], gap="large")
        with a:
            html(ui.task_card(t["name"], TEST_LABEL[t.test], t.due_date, int(t.days_left), t.status, status_text(t),
                              t.responsible_trust, bool(t.requires_call and not t.patient_called),
                              t.review_state == "needs_review"))
            if t.requires_call and not t.patient_called:
                st.error("Urgent finding: a clinician must phone this patient. No automated message is sent.")
            st.markdown(f"**What the AI read** (verbatim, from the {t.modality.lower()} report of {t.report_date})")
            st.info(t.evidence)
            st.caption(f"Urgency {t.urgency} · AI confidence {t.confidence:.2f} · "
                       f"{t.review_state.replace('_', ' ')}")
            with st.expander("Full report"):
                st.text(t.report_text)
            views = rules.trust_views(conn, conn.execute("SELECT * FROM tasks WHERE id=?", (int(t.id),)).fetchone())
            html(ui.lanes("Who can see this follow-up", "Each hospital's record only sees its own bookings.",
                          [(tr.split()[0], "own record", view_state(views[tr]), views[tr]) for tr in TRUSTS]
                          + [("Resultwise", "all trusts", t.status, status_text(t))]))
        with b:
            if t.status not in ("completed", "dismissed"):
                if st.button("Confirm follow-up", key=f"cf{t.id}", type="primary", width="stretch"):
                    pipeline.confirm_task(conn, int(t.id))
                    st.rerun()
                if t.requires_call and not t.patient_called and st.button("Mark patient phoned", key=f"ph{t.id}",
                                                                           width="stretch"):
                    pipeline.mark_called(conn, int(t.id))
                    st.rerun()
                with st.expander("Correct the AI"):
                    nd = st.date_input("Due date", value=date.fromisoformat(t.due_date), key=f"nd{t.id}")
                    nu = st.selectbox("Urgency", ["routine", "soon", "urgent"],
                                      index=["routine", "soon", "urgent"].index(t.urgency), key=f"nu{t.id}")
                    if st.button("Save correction", key=f"sv{t.id}"):
                        pipeline.edit_task(conn, int(t.id), nd.isoformat(), nu)
                        st.rerun()
                with st.expander("Dismiss (reason required)"):
                    reason = st.selectbox("Reason", DISMISS_REASONS, key=f"rs{t.id}")
                    note = st.text_input("Note", key=f"nt{t.id}")
                    if st.button("Dismiss task", key=f"ds{t.id}"):
                        pipeline.dismiss_task(conn, int(t.id), reason + (f": {note}" if note else ""))
                        st.rerun()
            if t.requires_call:
                st.caption("Urgent tasks never get an automated patient message.")
            elif st.button(f"Preview patient message ({t.language})", key=f"pv{t.id}", width="stretch"):
                p = dict(conn.execute("SELECT * FROM patients WHERE id=?", (t.patient_id,)).fetchone())
                phone_no = rules.TRUST_PHONE.get(t.responsible_trust, p["phone"])
                en, facts = messages.draft_english(p, dict(t), phone_no)
                if p["language"] == "English":
                    tr, back, ok, notes = None, "", True, []
                else:
                    tr, back = messages.translate(en, facts, t.test, p["language"], engine, key, inject)
                    ok, notes = messages.fact_check(en, tr, facts)
                html(ui.message_card(p["name"], TEST_LABEL[t.test], p["language"], p["channel"], en, tr, back, ok,
                                     " ".join(notes)))
                st.caption("Preview only. Nothing is sent until the follow-up is overdue and a clinician approves it.")

elif page == "Patient journey":
    html(ui.header("One patient, two hospitals",
                   "Each hospital's own record only sees its own bookings. Resultwise follows the patient across both."))
    pts = q("SELECT DISTINCT p.id, p.name FROM patients p JOIN tasks t ON t.patient_id=p.id ORDER BY p.id")
    labels = {f"{r['name']} ({r['id']})": r["id"] for _, r in pts.iterrows()}
    default = next((i for i, k in enumerate(labels) if "P001" in k), 0)
    pid = labels[st.selectbox("Patient", list(labels), index=default)]
    p = conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    st.markdown(f"**{p['name']}**, {p['age']}. Prefers {p['language']}, contact by {p['channel']}. "
                f"Registered at {p['home_trust']}.")
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
                   "Every output is checked before it reaches a clinician.", tag=f"Engine: {engine_label}"))
    new = q("SELECT id, patient_id, report_date, modality, text FROM reports WHERE processed=0 ORDER BY report_date")
    if new.empty:
        st.success("All reports processed.")
    else:
        if st.button(f"Read all {len(new)} new reports", type="primary"):
            for rid in new.id:
                pipeline.process_report(conn, rid, engine, key)
            st.rerun()
        for _, r in new.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r.modality}** · report {r.id} · patient {r.patient_id} · {r.report_date}")
                st.text(r.text)
                if st.button("Read this report", key=f"pr{r.id}"):
                    res, created = pipeline.process_report(conn, r.id, engine, key)
                    st.session_state["last_result"] = (r.id, res.extraction.model_dump(), res.issues, res.engine_used)
                    st.rerun()
    if "last_result" in st.session_state:
        rid, ex, issues, used = st.session_state["last_result"]
        st.subheader(f"What the AI extracted from {rid}")
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
               "Conclusion: Borderline fall in function. Repeat echo in 4 weeks and cardio-oncology review if further decline.")
    text = st.text_area("Report text (synthetic only, never real patient data)", example, height=140)
    if st.button("Extract follow-ups", type="primary"):
        rid, res, created = pipeline.add_pasted_report(conn, pid, text, modality, engine, key)
        st.success(f"Report {rid}: {len(created)} task(s) created ({res.engine_used}).")
        st.json(res.extraction.model_dump())
        for i in res.issues:
            st.warning(i)

elif page == "Patient view":
    html(ui.header("What the patient receives",
                   "Sent only after a clinician approves it. It names the test and how to book, never a diagnosis."))
    sent = q("""SELECT m.*, p.name, t.responsible_trust FROM messages m JOIN patients p ON p.id=m.patient_id
                JOIN tasks t ON t.id=m.task_id WHERE m.status='sent' ORDER BY m.id DESC""")
    if sent.empty:
        html('<div class="rw-hint">No messages sent yet. Click <b>+2 wk</b> so a follow-up goes overdue, then approve a '
             'message on the Worklist.</div>')
    else:
        names = {f"{r['name']} ({r['patient_id']})": r["patient_id"] for _, r in sent.iterrows()}
        pid = names[st.selectbox("Patient", list(names))]
        channel_note = {"app": "Patient app message", "letter": "Posted letter",
                        "carer": "Sent to the registered carer, with the patient's recorded consent",
                        "phone": "Read out by staff as a phone call script"}
        for _, m in sent[sent.patient_id == pid].iterrows():
            has_tr = not pd.isna(m["text_translated"]) and bool(m["text_translated"])
            show_en = st.toggle("Show English version", key=f"en{m['id']}", value=not has_tr) if has_tr else True
            text = m["text_en"] if show_en else m["text_translated"]
            lang = "English" if show_en else m["language"]
            st.caption(f"{channel_note.get(m['channel'], m['channel'])} · sent {m['sent_on']} · approved by {m['approved_by']}")
            if m["channel"] == "app":
                html(ui.phone(text, lang, f"Your care team, {m['responsible_trust']}"))
            else:
                html(ui.letter(text, lang, m["name"], m["responsible_trust"]))
            st.write("")

elif page == "Equity":
    html(ui.header("Who is the system failing to reach?",
                   "On-time follow-up across 900 past synthetic follow-ups. The dashed line is the overall rate.",
                   tag="Synthetic, with a built-in disparity"))
    hist = pd.read_csv(pipeline.DATA / "history.csv")
    overall = hist.completed_on_time.mean()

    def bar(col, title, order=None):
        g = hist.groupby(col).agg(rate=("completed_on_time", "mean"), n=("completed_on_time", "size")).reset_index()
        g[col] = g[col].astype(str)
        g["below"] = g.rate < overall - 0.03
        base = alt.Chart(g).encode(
            y=alt.Y(f"{col}:N", sort=order, title=None),
            x=alt.X("rate:Q", title=None, axis=alt.Axis(format="%", grid=False), scale=alt.Scale(domain=[0, 1])),
            tooltip=[alt.Tooltip(f"{col}:N", title=title), alt.Tooltip("rate:Q", format=".0%", title="On time"),
                     alt.Tooltip("n:Q", title="Follow-ups")])
        bars = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
            color=alt.condition("datum.below", alt.value(ui.RED), alt.value(ui.TEAL)))
        labels = base.mark_text(align="left", dx=5, color=ui.MUTED).encode(text=alt.Text("rate:Q", format=".0%"))
        rule = alt.Chart(pd.DataFrame({"x": [overall]})).mark_rule(strokeDash=[4, 3], color=ui.INK).encode(x="x:Q")
        return (bars + labels + rule).properties(title=title, height=alt.Step(30)).configure_view(stroke=None)

    st.markdown(f"**{overall:.0%}** of follow-ups were completed on time overall. Groups in red are well below that.")
    c1, c2, c3 = st.columns(3)
    c1.altair_chart(bar("age_band", "Age", ["<50", "50-64", "65-79", "80+"]), width="stretch")
    c2.altair_chart(bar("language", "Preferred language"), width="stretch")
    hist["imd_quintile"] = hist.imd_quintile.map(lambda v: f"{v}{' (most deprived)' if v == 1 else ''}")
    c3.altair_chart(bar("imd_quintile", "Deprivation quintile"), width="stretch")
    html('<div class="rw-hint">What to do with this: change the outreach for the red groups. For example, phone first '
         'for patients over 80, translated letters, and contacting carers. Then measure again.</div>')
    with st.expander("Table view"):
        st.dataframe(hist.groupby(["age_band", "language"]).completed_on_time.agg(["mean", "size"])
                     .rename(columns={"mean": "on-time rate", "size": "follow-ups"}).round(2))

elif page == "Evaluation":
    html(ui.header("How accurate is the AI?",
                   "Recall: did it miss a follow-up? That is the safety number. "
                   "Precision: is it raising false alarms?", tag=f"Engine: {engine_label}"))
    a, b = st.columns(2)
    which = a.radio("Report set", ["heldout", "development"], horizontal=True,
                    format_func=lambda s: {"development": "Development (28 reports)",
                                           "heldout": "Held-out (10 unseen reports)"}[s])
    if b.button("Run evaluation", type="primary"):
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
    html(ui.header("Audit log", "Every AI output, rule decision and human action, newest first."))
    st.dataframe(q("SELECT id, sim_date AS date, actor AS who, action AS event, task_id AS task, detail "
                   "FROM audit ORDER BY id DESC"), hide_index=True, width="stretch")
