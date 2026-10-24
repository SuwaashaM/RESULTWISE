"""Resultwise: follow-up safety net demo (Streamlit).

Run:  streamlit run app.py
All data is synthetic. Nothing here is a medical device; it is a hackathon prototype.
"""
import json
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from resultwise import db, llm, pipeline, rules
from resultwise.evaluate import evaluate, load_set
from resultwise.schema import PLAIN_TEST_NAME

st.set_page_config(page_title="Resultwise", layout="wide")

BLUE = "#2a78d6"
STATUS_LABEL = {
    "open": "Open", "due_soon": "Due soon, not booked", "booked": "Booked", "completed": "Completed",
    "overdue": "Overdue", "dismissed": "Dismissed",
}
TEST_LABEL = {k: v[0].upper() + v[1:] for k, v in PLAIN_TEST_NAME.items()}
DISMISS_REASONS = ["Not clinically indicated", "Already done elsewhere", "Patient declined (documented)",
                   "AI extraction error", "Duplicate task", "Other"]


@st.cache_resource
def get_conn():
    c = db.connect()
    pipeline.ensure_db(c)
    return c


conn = get_conn()


def q(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("Resultwise")
    st.caption("No follow-up silently lost. Synthetic demo data only.")
    today = db.today(conn)
    st.metric("Simulated date", date.fromisoformat(today).strftime("%a %d %b %Y"))

    engine_label = st.selectbox("AI engine", ["Offline (no key needed)", "Claude", "OpenAI"])
    engine = {"Offline (no key needed)": "offline", "Claude": "claude", "OpenAI": "openai"}[engine_label]
    key = None
    if engine != "offline":
        key = st.text_input(f"{engine_label} API key", type="password",
                            help="Kept in this browser session only. Or set ANTHROPIC_API_KEY / OPENAI_API_KEY.") or None
        if not llm.available_key(engine, key):
            st.warning("No key found: Resultwise will fall back to offline mode and flag tasks for review.")
    inject = st.toggle("Simulate a translation error", help="Changes the date in new translations, to show the safety check blocking it.")

    st.write("**Move time forward**")
    c1, c2, c3 = st.columns(3)
    for col, (lbl, days) in zip((c1, c2, c3), (("+1 wk", 7), ("+2 wk", 14), ("+4 wk", 28))):
        if col.button(lbl, width="stretch"):
            rules.advance(conn, days, engine, key, inject)
            st.rerun()
    if st.button("Reset demo", width="stretch"):
        pipeline.reset_demo(conn)
        st.session_state.clear()
        st.rerun()

    page = st.radio("View", ["Clinician worklist", "Patient journey (two trusts)", "Report inbox",
                             "Patient view", "Equity", "Evaluation", "Audit log"])


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
        s += " · nurse outreach" if r["escalation_level"] >= 2 else " · clinician alerted"
    return s


# ----------------------------------------------------------------------------- pages
if page == "Clinician worklist":
    st.header("Clinician worklist")
    df = tasks_df()
    msgs = q("""SELECT m.*, p.name, t.test, t.due_date FROM messages m JOIN patients p ON p.id=m.patient_id
                JOIN tasks t ON t.id=m.task_id WHERE m.status IN ('pending_approval','blocked') ORDER BY m.id""")
    live = df[~df.status.isin(["completed", "dismissed"])] if not df.empty else df
    k = st.columns(5)
    k[0].metric("Urgent: phone patient", int(((live.requires_call == 1) & (live.patient_called == 0)).sum()))
    k[1].metric("Overdue, no booking", int((live.status == "overdue").sum()))
    k[2].metric("Needs human review", int((live.review_state == "needs_review").sum()))
    k[3].metric("Messages to approve", len(msgs))
    k[4].metric("Loops closed", int((df.status == "completed").sum()) if not df.empty else 0)

    if len(msgs):
        st.subheader("Patient messages awaiting approval")
        for _, m in msgs.iterrows():
            with st.container(border=True):
                head = f"**{m['name']}** · {TEST_LABEL[m['test']]} · {m['language']} via {m['channel']}"
                st.markdown(head)
                cols = st.columns(2 if m["text_translated"] else 1)
                cols[0].caption("English (what the clinician approves)")
                cols[0].write(m["text_en"])
                if m["text_translated"]:
                    cols[1].caption(f"{m['language']} translation")
                    cols[1].write(m["text_translated"])
                    if m["back_translation"]:
                        cols[1].caption("Back-translation: " + m["back_translation"])
                if m["check_passed"]:
                    st.success("Translation check passed: date, phone number and name preserved.")
                elif m["status"] == "blocked":
                    st.error("BLOCKED by translation check: " + m["check_notes"].replace("\n", " "))
                b1, b2, b3 = st.columns([1, 1, 4])
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

    st.subheader("Follow-up tasks")
    if df.empty:
        st.info("No tasks yet. Process reports in the Report inbox.")
    else:
        show_closed = st.toggle("Show completed and dismissed", value=False)
        view = df if show_closed else live
        table = pd.DataFrame({
            "Task": view.id, "Patient": view.name, "Test": view.test.map(TEST_LABEL), "Due": view.due_date,
            "Days left": view.days_left,
            "Status": view.apply(status_text, axis=1),
            "Urgency": view.urgency, "Review": view.review_state.str.replace("_", " "),
            "Call needed": view.apply(lambda r: "YES" if r.requires_call and not r.patient_called else "", axis=1),
            "Follow-up at": view.responsible_trust,
        })
        st.dataframe(table, hide_index=True, width="stretch")

        options = {f"#{r.id} · {r['name']} · {TEST_LABEL[r.test]}": int(r.id) for _, r in view.iterrows()}
        if options:
            choice = st.selectbox("Open a task", list(options))
            t = df[df.id == options[choice]].iloc[0]
            with st.container(border=True):
                st.markdown(f"### {t['name']}: {TEST_LABEL[t.test]}")
                a, b, c = st.columns(3)
                a.write(f"**Status:** {status_text(t)}")
                a.write(f"**Due:** {t.due_date} ({t.days_left} days)")
                b.write(f"**Urgency:** {t.urgency}")
                b.write(f"**AI confidence:** {t.confidence:.2f} · review: {t.review_state.replace('_', ' ')}")
                c.write(f"**Report:** {t.report_id} ({t.modality}, {t.report_date})")
                c.write(f"**Follow-up at:** {t.responsible_trust}")
                if t.requires_call and not t.patient_called:
                    st.error("Urgent finding: a clinician must phone this patient. No automated message is sent.")
                st.markdown("**Evidence the AI used** (verbatim from the report):")
                st.info(t.evidence)
                with st.expander("Full report"):
                    st.text(t.report_text)
                views = rules.trust_views(conn, conn.execute("SELECT * FROM tasks WHERE id=?", (int(t.id),)).fetchone())
                st.markdown("**What each system can see**")
                v1, v2, v3 = st.columns(3)
                v1.caption("Northbridge's own record")
                v1.write(views["Northbridge Hospitals"])
                v2.caption("Valeford's own record")
                v2.write(views["Valeford Hospitals"])
                v3.caption("Resultwise (all trusts)")
                v3.write(status_text(t))

                if t.status not in ("completed", "dismissed"):
                    x1, x2, x3 = st.columns(3)
                    if x1.button("Confirm follow-up", key=f"cf{t.id}", type="primary"):
                        pipeline.confirm_task(conn, int(t.id))
                        st.rerun()
                    if t.requires_call and not t.patient_called and x2.button("Mark patient phoned", key=f"ph{t.id}"):
                        pipeline.mark_called(conn, int(t.id))
                        st.rerun()
                    with st.expander("Correct the AI"):
                        nd = st.date_input("Due date", value=date.fromisoformat(t.due_date), key=f"nd{t.id}")
                        nu = st.selectbox("Urgency", ["routine", "soon", "urgent"],
                                          index=["routine", "soon", "urgent"].index(t.urgency), key=f"nu{t.id}")
                        if st.button("Save correction", key=f"sv{t.id}"):
                            pipeline.edit_task(conn, int(t.id), nd.isoformat(), nu)
                            st.rerun()
                    with st.expander("Dismiss (a reason is required)"):
                        reason = st.selectbox("Reason", DISMISS_REASONS, key=f"rs{t.id}")
                        note = st.text_input("Note", key=f"nt{t.id}")
                        if st.button("Dismiss task", key=f"ds{t.id}"):
                            pipeline.dismiss_task(conn, int(t.id), reason + (f": {note}" if note else ""))
                            st.rerun()

elif page == "Patient journey (two trusts)":
    st.header("Patient journey across two trusts")
    st.caption("Each hospital's own system only sees its own bookings. Resultwise follows the patient across both.")
    pts = q("SELECT DISTINCT p.id, p.name FROM patients p JOIN tasks t ON t.patient_id=p.id ORDER BY p.id")
    labels = {f"{r['name']} ({r['id']})": r["id"] for _, r in pts.iterrows()}
    default = next((i for i, k in enumerate(labels) if "P001" in k), 0)
    pid = labels[st.selectbox("Patient", list(labels), index=default)]
    p = conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    st.write(f"**{p['name']}**, {p['age']} · prefers {p['language']} · contact: {p['channel']} · home trust: {p['home_trust']}")
    for t in conn.execute("SELECT * FROM tasks WHERE patient_id=? ORDER BY due_date", (pid,)).fetchall():
        rep = conn.execute("SELECT * FROM reports WHERE id=?", (t["report_id"],)).fetchone()
        views = rules.trust_views(conn, t)
        with st.container(border=True):
            st.markdown(f"**{TEST_LABEL[t['test']]}** due {t['due_date']} · recommended in {rep['modality'].lower()} "
                        f"report at {rep['source_trust']} on {rep['report_date']} · to be done at {rep['follow_up_trust']}")
            cols = st.columns(3)
            for col, trust in zip(cols[:2], ("Northbridge Hospitals", "Valeford Hospitals")):
                col.caption(f"{trust.split()[0]}'s own system")
                txt = views[trust]
                if "OVERDUE" in txt:
                    col.error(txt)
                elif "No record" in txt or "not tracked" in txt:
                    col.warning(txt)
                else:
                    col.success(txt)
            cols[2].caption("Resultwise")
            s = status_text(t)
            (cols[2].error if t["status"] == "overdue" else cols[2].success if t["status"] in ("booked", "completed")
             else cols[2].info)(s)
    audit = q("""SELECT a.sim_date AS date, a.actor, a.action, a.detail FROM audit a JOIN tasks t ON t.id=a.task_id
                 WHERE t.patient_id=? ORDER BY a.id""", (pid,))
    st.subheader("Timeline")
    st.dataframe(audit, hide_index=True, width="stretch")

elif page == "Report inbox":
    st.header("Report inbox")
    st.caption(f"Engine: {engine_label}. The AI only reads and structures the report; clinicians decide.")
    new = q("SELECT id, patient_id, report_date, modality, text FROM reports WHERE processed=0 ORDER BY report_date")
    if new.empty:
        st.success("All reports processed.")
    else:
        if st.button(f"Process all {len(new)} new reports", type="primary"):
            for rid in new.id:
                pipeline.process_report(conn, rid, engine, key)
            st.rerun()
        for _, r in new.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r.id}** · {r.patient_id} · {r.modality} · {r.report_date}")
                st.text(r.text)
                if st.button("Process", key=f"pr{r.id}"):
                    res, created = pipeline.process_report(conn, r.id, engine, key)
                    st.session_state["last_result"] = (r.id, res.extraction.model_dump(), res.issues, res.engine_used)
                    st.rerun()
    if "last_result" in st.session_state:
        rid, ex, issues, used = st.session_state["last_result"]
        st.subheader(f"Last extraction: {rid} ({used})")
        st.json(ex)
        for i in issues:
            st.warning(i)

    st.subheader("Try any report")
    pts = q("SELECT id, name FROM patients ORDER BY id")
    pmap = {f"{r['name']} ({r['id']})": r["id"] for _, r in pts.iterrows()}
    pid = pmap[st.selectbox("Patient", list(pmap), key="paste_patient")]
    modality = st.text_input("Modality", "Echocardiogram")
    example = ("Echocardiogram.\nFindings: LVEF 52%, down from 60%. GLS -16%.\n"
               "Conclusion: Borderline fall in function. Repeat echo in 4 weeks and cardio-oncology review if further decline.")
    text = st.text_area("Report text (synthetic only, never real patient data)", example, height=140)
    if st.button("Extract follow-ups"):
        rid, res, created = pipeline.add_pasted_report(conn, pid, text, modality, engine, key)
        st.success(f"Report {rid}: {len(created)} task(s) created ({res.engine_used}).")
        st.json(res.extraction.model_dump())
        for i in res.issues:
            st.warning(i)

elif page == "Patient view":
    st.header("What the patient receives")
    st.caption("Mock patient app / letter. Messages never name a diagnosis and are sent only after clinician approval.")
    sent = q("""SELECT m.*, p.name FROM messages m JOIN patients p ON p.id=m.patient_id WHERE m.status='sent' ORDER BY m.id DESC""")
    if sent.empty:
        st.info("No messages sent yet. Move time forward until a follow-up is overdue, then approve a message in the worklist.")
    else:
        names = {f"{r['name']} ({r['patient_id']})": r["patient_id"] for _, r in sent.iterrows()}
        pid = names[st.selectbox("Patient", list(names))]
        channel_note = {"app": "Patient app notification (preview text: 'You have a new message from your care team')",
                        "letter": "Printed and posted as a letter",
                        "carer": "Sent to the registered carer, with the patient's recorded consent",
                        "phone": "Read out by staff as a phone call script"}
        for _, m in sent[sent.patient_id == pid].iterrows():
            st.caption(f"{channel_note.get(m['channel'], m['channel'])} · sent {m['sent_on']} · approved by {m['approved_by']}")
            left, _ = st.columns([2, 3])
            with left.container(border=True):
                show_en = st.toggle("Show English", key=f"en{m['id']}", value=not m["text_translated"])
                st.write(m["text_en"] if show_en or not m["text_translated"] else m["text_translated"])

elif page == "Equity":
    st.header("Who is the system failing to reach?")
    st.caption("900 past synthetic follow-ups. A disparity was deliberately built into this synthetic data so the "
               "feature has something to show. Real use would measure it on real outcomes.")
    hist = pd.read_csv(pipeline.DATA / "history.csv")
    overall = hist.completed_on_time.mean()
    st.metric("Follow-ups completed on time (overall)", f"{overall:.0%}")

    def bar(col, title, order=None):
        g = hist.groupby(col).agg(rate=("completed_on_time", "mean"), n=("completed_on_time", "size")).reset_index()
        g[col] = g[col].astype(str)
        base = alt.Chart(g).encode(
            y=alt.Y(f"{col}:N", sort=order, title=None),
            x=alt.X("rate:Q", title="Completed on time", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
            tooltip=[alt.Tooltip(f"{col}:N", title=title), alt.Tooltip("rate:Q", format=".0%", title="On time"),
                     alt.Tooltip("n:Q", title="Follow-ups")])
        bars = base.mark_bar(color=BLUE, cornerRadiusEnd=4, height=18)
        labels = base.mark_text(align="left", dx=4, color="#52514e").encode(text=alt.Text("rate:Q", format=".0%"))
        rule = alt.Chart(pd.DataFrame({"x": [overall]})).mark_rule(strokeDash=[4, 3], color="#52514e").encode(x="x:Q")
        return (bars + labels + rule).properties(title=title, height=alt.Step(28))

    c1, c2, c3 = st.columns(3)
    c1.altair_chart(bar("age_band", "Age band", ["<50", "50-64", "65-79", "80+"]), width="stretch")
    c2.altair_chart(bar("language", "Preferred language"), width="stretch")
    hist["imd_quintile"] = hist.imd_quintile.map(lambda v: f"{v}{' (most deprived)' if v == 1 else ''}")
    c3.altair_chart(bar("imd_quintile", "Deprivation quintile"), width="stretch")
    st.caption("Dashed line = overall rate. Hover a bar for the number of follow-ups.")
    with st.expander("Table view"):
        st.dataframe(hist.groupby(["age_band", "language"]).completed_on_time.agg(["mean", "size"])
                     .rename(columns={"mean": "on-time rate", "size": "follow-ups"}).round(2))
    st.info("How this is used: pick the groups below the line and change the outreach, for example phone first "
            "for patients over 80, translated letters, carer contact. Then re-measure.")

elif page == "Evaluation":
    st.header("How accurate is the extraction?")
    st.caption("Recall = did we miss a follow-up (the safety metric). Precision = are we crying wolf.")
    a, b = st.columns(2)
    which = a.radio("Report set", ["development", "heldout"], horizontal=True,
                    format_func=lambda s: {"development": "Development (28 reports)",
                                           "heldout": "Held-out (10 unseen reports)"}[s])
    if b.button("Run evaluation", type="primary"):
        st.session_state["eval"] = evaluate(load_set(which), engine, key)
    if which == "development":
        st.warning("The offline rules were written while looking at the development set, so their score there is "
                   "optimistic. The held-out set is the honest test.")
    m = st.session_state.get("eval")
    if m:
        cols = st.columns(5)
        for col, (lbl, k_) in zip(cols, (("Recall", "recall"), ("Precision", "precision"),
                                         ("Urgent recall", "urgent_recall"), ("Timeframe", "timeframe_accuracy"),
                                         ("Urgency", "urgency_accuracy"))):
            col.metric(lbl, "n/a" if m[k_] is None else f"{m[k_]:.0%}")
        st.caption(f"Engine: {m['engine']} · {m['n_reports']} reports · {m['gold_items']} labelled follow-ups · "
                   f"{m['predicted_items']} predicted")
        st.dataframe(pd.DataFrame(m["rows"]), hide_index=True, width="stretch")

elif page == "Audit log":
    st.header("Audit log")
    st.caption("Every AI output, rule decision and human action, in order. Accountability by design.")
    st.dataframe(q("SELECT id, sim_date AS date, actor, action, task_id AS task, detail FROM audit ORDER BY id DESC"),
                 hide_index=True, width="stretch")
