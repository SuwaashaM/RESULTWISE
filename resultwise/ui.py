"""Visual layer for the Streamlit app: one typeface (Atkinson Hyperlegible, designed for low-vision legibility),
an ink-teal clinical palette, and a few HTML components. The signature element is the "loop strip": every
follow-up in the system shown as one segmented bar, from closed loops to overdue gaps.
"""
import html

INK = "#0B2E36"       # sidebar, headings
PAPER = "#F6F9F9"     # page
LINE = "#D6E1E3"
TEAL = "#0F7C6E"      # loop closed / primary
SKY = "#3B6EA8"       # booked / open
AMBER = "#A85A00"     # due soon
RED = "#B42318"       # overdue
MUTED = "#5B6B70"

STATUS_STYLE = {
    "completed": (TEAL, "#E3F2EF", "Loop closed"),
    "booked": (SKY, "#E8EFF8", "Booked"),
    "open": ("#4B5A5E", "#EDF1F2", "Open"),
    "due_soon": (AMBER, "#FBF0E1", "Due soon, not booked"),
    "overdue": (RED, "#FBE9E7", "Overdue"),
    "dismissed": ("#6B7280", "#F1F2F3", "Dismissed"),
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {{
  font-family: 'Atkinson Hyperlegible', system-ui, sans-serif !important; }}
.stApp {{ background: {PAPER}; }}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; max-width: 1240px; }}
h1, h2, h3 {{ color: {INK}; letter-spacing: -0.01em; }}
[data-testid="stSidebar"] {{ background: {INK}; }}
[data-testid="stSidebar"] * {{ color: #E6EEF0 !important; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{ padding:.15rem 0; }}
[data-testid="stSidebar"] .stButton button {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.18); }}
[data-testid="stSidebar"] .stButton button:hover {{ border-color: #7FD1C4; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{ background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.18); }}
.rw-brand {{ font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 .1rem; }}
.rw-brand .ring {{ display:inline-block; width:.85em; height:.85em; border:3px solid #7FD1C4; border-radius:50%;
  border-right-color: transparent; transform: rotate(-45deg); margin-right:.35em; vertical-align:-.08em; }}
.rw-date {{ font-size: 1.35rem; font-weight: 700; margin:.1rem 0 .6rem; }}
.rw-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; margin-bottom:1.1rem; }}
.rw-head h1 {{ font-size: 2.1rem; margin:0; line-height:1.1; }}
.rw-head p {{ margin:.35rem 0 0; color:{MUTED}; max-width: 62ch; }}
.rw-tag {{ font-size:.8rem; color:{MUTED}; border:1px solid {LINE}; border-radius:999px; padding:.2rem .7rem; white-space:nowrap; background:#fff; }}
.rw-loop {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:1rem 1.2rem 1.1rem; margin-bottom:1.4rem; }}
.rw-loop-title {{ display:flex; justify-content:space-between; color:{INK}; font-weight:700; margin-bottom:.6rem; }}
.rw-loop-title span {{ color:{MUTED}; font-weight:400; }}
.rw-bar {{ display:flex; height:22px; border-radius:6px; overflow:hidden; gap:2px; background:#fff; }}
.rw-bar div {{ height:100%; }}
.rw-legend {{ display:flex; flex-wrap:wrap; gap:1.2rem; margin-top:.7rem; font-size:.92rem; color:{INK}; }}
.rw-legend b {{ font-size:1.25rem; margin-right:.3rem; }}
.rw-legend i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:.4rem; vertical-align:middle; }}
.rw-card {{ background:#fff; border:1px solid {LINE}; border-left:5px solid var(--c); border-radius:10px;
  padding:.8rem 1rem; margin-bottom:.6rem; }}
.rw-card .top {{ display:flex; justify-content:space-between; gap:.6rem; align-items:baseline; }}
.rw-card .name {{ font-weight:700; color:{INK}; font-size:1.05rem; }}
.rw-card .test {{ color:{INK}; }}
.rw-card .meta {{ color:{MUTED}; font-size:.88rem; margin-top:.25rem; }}
.rw-pill {{ display:inline-block; font-size:.8rem; font-weight:700; padding:.15rem .6rem; border-radius:999px;
  color:var(--c); background:var(--bg); white-space:nowrap; }}
.rw-call {{ display:inline-block; font-size:.8rem; font-weight:700; padding:.15rem .6rem; border-radius:999px;
  color:#fff; background:{RED}; margin-left:.4rem; }}
.rw-msg {{ background:#fff; border:1px solid {LINE}; border-radius:12px; padding:1rem 1.1rem; margin-bottom:.4rem; }}
.rw-msg .who {{ font-weight:700; color:{INK}; }}
.rw-msg .lang {{ font-size:.8rem; border:1px solid {LINE}; border-radius:6px; padding:.1rem .45rem; margin-left:.4rem; color:{MUTED}; }}
.rw-msg .cols {{ display:grid; grid-template-columns: 1fr; gap:.8rem; margin-top:.7rem; }}
.rw-msg .cols.one {{ grid-template-columns: 1fr; }}
.rw-msg .label {{ font-size:.82rem; color:{MUTED}; margin-bottom:.25rem; }}
.rw-msg .text {{ line-height:1.55; color:#1C2B2F; }}
.rw-check {{ margin-top:.7rem; font-size:.9rem; font-weight:700; }}
.rw-check.ok {{ color:{TEAL}; }} .rw-check.bad {{ color:{RED}; }}
.rw-lanes {{ background:#fff; border:1px solid {LINE}; border-radius:12px; padding:1rem 1.1rem; margin-bottom:.9rem; }}
.rw-lanes .what {{ font-weight:700; color:{INK}; font-size:1.05rem; }}
.rw-lanes .why {{ color:{MUTED}; font-size:.9rem; margin:.2rem 0 .8rem; }}
.rw-lane {{ display:grid; grid-template-columns: 210px 1fr; align-items:center; gap:.8rem; padding:.5rem 0; border-top:1px solid {LINE}; }}
.rw-lane .who {{ color:{INK}; font-weight:700; font-size:.95rem; }}
.rw-lane .who small {{ display:block; color:{MUTED}; font-weight:400; }}
.rw-lane.us .who {{ color:{TEAL}; }}
.rw-state {{ display:inline-block; border-radius:8px; padding:.35rem .7rem; font-weight:700; font-size:.92rem;
  color:var(--c); background:var(--bg); }}
.rw-phone {{ width: 320px; border:10px solid {INK}; border-radius:34px; background:#fff; padding:1.2rem .9rem 1.6rem;
  box-shadow: 0 18px 40px rgba(11,46,54,.18); }}
.rw-phone .notch {{ width:90px; height:6px; border-radius:6px; background:{LINE}; margin:0 auto 1rem; }}
.rw-phone .from {{ font-size:.8rem; color:{MUTED}; margin-bottom:.4rem; }}
.rw-phone .bubble {{ background:#EAF4F2; border-radius:16px 16px 16px 4px; padding:.8rem .9rem; line-height:1.55; color:#1C2B2F; }}
.rw-letter {{ max-width: 520px; background:#fff; border:1px solid {LINE}; padding:1.6rem 1.8rem; line-height:1.65;
  box-shadow: 0 10px 30px rgba(11,46,54,.10); }}
.rw-hint {{ border:1px dashed {TEAL}; background:#F0F8F6; color:{INK}; border-radius:10px; padding:.7rem 1rem; margin:.4rem 0 1rem; }}
</style>
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def text_dir(language: str) -> str:
    return "rtl" if language in ("Urdu", "Arabic") else "ltr"


def pill(status: str, label: str | None = None) -> str:
    c, bg, default = STATUS_STYLE.get(status, STATUS_STYLE["open"])
    return f'<span class="rw-pill" style="--c:{c};--bg:{bg}">{esc(label or default)}</span>'


def header(title: str, lead: str, tag: str = "Synthetic data only") -> str:
    return (f'<div class="rw-head"><div><h1>{esc(title)}</h1><p>{esc(lead)}</p></div>'
            f'<span class="rw-tag">{esc(tag)}</span></div>')


def loop_strip(counts: dict) -> str:
    order = [("completed", "Loops closed"), ("booked", "Booked"), ("open", "Open"),
             ("due_soon", "Due soon, not booked"), ("overdue", "Overdue")]
    total = sum(counts.get(k, 0) for k, _ in order) or 1
    segs = "".join(
        f'<div title="{esc(lbl)}: {counts.get(k, 0)}" style="flex:{counts.get(k, 0)};background:{STATUS_STYLE[k][0]}"></div>'
        for k, lbl in order if counts.get(k, 0))
    legend = "".join(
        f'<span><i style="background:{STATUS_STYLE[k][0]}"></i><b>{counts.get(k, 0)}</b>{esc(lbl)}</span>'
        for k, lbl in order)
    return (f'<div class="rw-loop"><div class="rw-loop-title">Every follow-up in the system'
            f'<span>{total} tracked</span></div><div class="rw-bar">{segs}</div>'
            f'<div class="rw-legend">{legend}</div></div>')


def task_card(name, test, due, days_left, status, status_label, trust, call_needed=False, review=False) -> str:
    c = STATUS_STYLE.get(status, STATUS_STYLE["open"])[0]
    when = f"{abs(days_left)} days overdue" if days_left < 0 else ("due today" if days_left == 0 else f"due in {days_left} days")
    extra = '<span class="rw-call">Phone patient</span>' if call_needed else ""
    rev = " · AI output needs human review" if review else ""
    return (f'<div class="rw-card" style="--c:{c}"><div class="top"><div><span class="name">{esc(name)}</span>'
            f' <span class="test">· {esc(test)}</span></div><div>{pill(status, status_label)}{extra}</div></div>'
            f'<div class="meta">Due {esc(due)}, {esc(when)} · follow-up at {esc(trust)}{esc(rev)}</div></div>')


def message_card(name, test, language, channel, text_en, text_tr, back, ok, notes) -> str:
    cols = f'<div class="label">English (what you approve)</div><div class="text">{esc(text_en)}</div>'
    if text_tr:
        body = (f'<div class="cols"><div>{cols}</div><div><div class="label">{esc(language)} (what the patient reads)</div>'
                f'<div class="text" dir="{text_dir(language)}">{esc(text_tr)}</div>'
                + (f'<div class="label" style="margin-top:.6rem">Back-translation: {esc(back)}</div>' if back else "")
                + "</div></div>")
    else:
        body = f'<div class="cols one"><div>{cols}</div></div>'
    check = (f'<div class="rw-check ok">Translation check passed: date, phone number and name are unchanged.</div>' if ok
             else f'<div class="rw-check bad">Blocked: {esc(notes)}</div>')
    return (f'<div class="rw-msg"><span class="who">{esc(name)}</span> · {esc(test)}'
            f'<span class="lang">{esc(language)}</span><span class="lang">{esc(channel)}</span>{body}'
            + (check if text_tr else "") + "</div>")


def lanes(title: str, why: str, rows: list[tuple[str, str, str, str]]) -> str:
    """rows: (who, sub, state_key, text)."""
    out = [f'<div class="rw-lanes"><div class="what">{esc(title)}</div><div class="why">{esc(why)}</div>']
    for who, sub, key, txt in rows:
        c, bg, _ = STATUS_STYLE.get(key, STATUS_STYLE["open"])
        cls = "rw-lane us" if who == "Resultwise" else "rw-lane"
        out.append(f'<div class="{cls}"><div class="who">{esc(who)}<small>{esc(sub)}</small></div>'
                   f'<div><span class="rw-state" style="--c:{c};--bg:{bg}">{esc(txt)}</span></div></div>')
    out.append("</div>")
    return "".join(out)


def phone(text: str, language: str, sender: str) -> str:
    return (f'<div class="rw-phone"><div class="notch"></div><div class="from">{esc(sender)}</div>'
            f'<div class="bubble" dir="{text_dir(language)}">{esc(text)}</div></div>')


def letter(text: str, language: str, name: str, trust: str) -> str:
    return (f'<div class="rw-letter" dir="{text_dir(language)}"><div style="color:{MUTED};margin-bottom:1rem">'
            f'{esc(trust)}<br>To: {esc(name)}</div>{esc(text)}</div>')


PORTAL_CSS = """
<style>
.rw-portal { --fs: 1.05rem; font-size: var(--fs); }
.rw-portal .hello { font-size: calc(var(--fs) * 1.9); font-weight:700; color:#0B2E36; margin:.2rem 0 .3rem; }
.rw-portal .sub { color:#5B6B70; margin-bottom:1rem; }
.rw-portal .msg { background:#fff; border:1px solid #D6E1E3; border-left:6px solid #0F7C6E; border-radius:14px;
  padding:1.3rem 1.4rem; line-height:1.7; color:#1C2B2F; white-space:pre-line; max-width: 68ch; }
.rw-portal .from { font-size:.85em; color:#5B6B70; margin-bottom:.5rem; }
.rw-portal.hc .msg { background:#000; color:#FFF; border-color:#FFD400; border-left-color:#FFD400; }
.rw-portal.hc .from, .rw-portal.hc .sub { color:#FFD400; }
.rw-portal.hc .hello { color:#000; }
.rw-portal .note { font-size:.85em; color:#5B6B70; margin-top:.5rem; max-width: 68ch; }
.rw-report { background:#fff; border:1px solid #D6E1E3; border-radius:10px; padding:1rem 1.2rem;
  font-family: 'Atkinson Hyperlegible', system-ui, sans-serif; white-space:pre-wrap; line-height:1.55; font-size:.92rem;
  color:#1C2B2F; max-height: 420px; overflow:auto; }
.rw-report mark { background:#FFE89A; padding:0 .15em; border-radius:3px; }
.rw-reply { background:#fff; border:1px solid #D6E1E3; border-left:5px solid #3B6EA8; border-radius:10px;
  padding:.7rem 1rem; margin-bottom:.4rem; }
</style>
"""


def report_html(text: str, evidence: str | None) -> str:
    body = esc(text)
    if evidence:
        ev = esc(evidence)
        if ev in body:
            body = body.replace(ev, f"<mark>{ev}</mark>", 1)
    return f'<div class="rw-report">{body}</div>'


def portal_message(text: str, language: str, sender: str, size: float, high_contrast: bool, note: str = "") -> str:
    cls = "rw-portal hc" if high_contrast else "rw-portal"
    return (f'<div class="{cls}" style="--fs:{size}rem"><div class="msg" dir="{text_dir(language)}" lang="{esc(language)}">'
            f'<div class="from">{esc(sender)}</div>{esc(text)}</div>'
            + (f'<div class="note">{esc(note)}</div>' if note else "") + "</div>")


def read_aloud_widget(text: str, lang_code: str, label: str = "Read aloud") -> str:
    import json
    return f"""
<div style="font-family:'Atkinson Hyperlegible',system-ui,sans-serif">
<button id="ra" style="font-size:1rem;padding:.55rem 1.1rem;border-radius:8px;border:1px solid #0F7C6E;
 background:#0F7C6E;color:#fff;cursor:pointer">{esc(label)}</button>
<button id="st" style="font-size:1rem;padding:.55rem 1.1rem;border-radius:8px;border:1px solid #D6E1E3;
 background:#fff;color:#0B2E36;cursor:pointer;margin-left:.4rem">Stop</button>
<span id="msg" style="margin-left:.6rem;color:#5B6B70;font-size:.9rem"></span>
<script>
const text = {json.dumps(text).replace("<", "\\u003c")}; const lang = {json.dumps(lang_code)};
document.getElementById('ra').onclick = () => {{
  if (!('speechSynthesis' in window)) {{ document.getElementById('msg').textContent = 'Read aloud is not supported in this browser.'; return; }}
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text); u.lang = lang; u.rate = 0.9;
  const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.toLowerCase().startsWith(lang.slice(0,2).toLowerCase()));
  if (v) u.voice = v; else document.getElementById('msg').textContent = 'No ' + lang + ' voice on this device; using the default voice.';
  speechSynthesis.speak(u);
}};
document.getElementById('st').onclick = () => speechSynthesis.cancel();
</script></div>"""


FLOW_CSS = f"""
<style>
.rw-flow {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:.5rem; margin-bottom:1rem; }}
.rw-flow div {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:.6rem .8rem; color:{INK};
  font-size:.92rem; line-height:1.35; }}
.rw-flow b {{ display:block; color:{TEAL}; font-size:.8rem; margin-bottom:.15rem; }}
.rw-steps {{ display:flex; gap:0; margin:.2rem 0 1rem; flex-wrap:wrap; }}
.rw-step {{ flex:1; min-width:150px; padding:.55rem .8rem; border:1px solid {LINE}; background:#fff; color:{MUTED};
  font-size:.9rem; }}
.rw-step:first-child {{ border-radius:10px 0 0 10px; }} .rw-step:last-child {{ border-radius:0 10px 10px 0; }}
.rw-step.done {{ background:#E3F2EF; color:{TEAL}; font-weight:700; border-color:#BFE3DB; }}
.rw-step.now {{ background:#FBF0E1; color:{AMBER}; font-weight:700; border-color:#F1D3A6; }}
.rw-todo div {{ display:flex; justify-content:space-between; align-items:center; background:#fff; border:1px solid {LINE};
  border-left:5px solid var(--c); border-radius:10px; padding:.6rem .9rem; margin-bottom:.45rem; color:{INK}; }}
.rw-todo b {{ font-size:1.3rem; }}
.rw-sum {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:.9rem 1rem; line-height:1.6; color:#1C2B2F; }}
.rw-sum .big {{ font-size:1.1rem; font-weight:700; color:{INK}; margin-bottom:.4rem; }}
.rw-sum dl {{ display:grid; grid-template-columns: 9rem 1fr; gap:.2rem .6rem; margin:.4rem 0 0; }}
.rw-sum dt {{ color:{MUTED}; }} .rw-sum dd {{ margin:0; }}
@media (max-width: 800px) {{ .rw-flow {{ grid-template-columns: 1fr 1fr; }} }}
</style>
"""


def flow_strip() -> str:
    steps = [("Step 1", "AI reads every scan report and lists the follow-ups"),
             ("Step 2", "You check the AI's result and approve the patient message"),
             ("Step 3", "Rules track the booking at every hospital and escalate gaps"),
             ("Step 4", "The patient reads the message in their language and can reply")]
    return FLOW_CSS + '<div class="rw-flow">' + "".join(f"<div><b>{a}</b>{esc(b)}</div>" for a, b in steps) + "</div>"


def stepper(steps: list[tuple[str, bool]]) -> str:
    out, now_set = [], False
    for label, done in steps:
        cls = "done" if done else ("now" if not now_set else "")
        if not done:
            now_set = True
        mark = "Done: " if done else ("Next: " if cls == "now" else "")
        out.append(f'<div class="rw-step {cls}">{mark}{esc(label)}</div>')
    return FLOW_CSS + '<div class="rw-steps">' + "".join(out) + "</div>"


def todo_list(items: list[tuple[str, int, str]]) -> str:
    rows = "".join(f'<div style="--c:{STATUS_STYLE[k][0] if n else LINE}"><span>{esc(lbl)}</span><b>{n}</b></div>'
                   for lbl, n, k in items)
    return FLOW_CSS + f'<div class="rw-todo">{rows}</div>'


def plain_summary(name, test, due, urgency, trust, confidence, evidence, review_state) -> str:
    when = {"urgent": "urgently", "soon": "soon", "routine": "routinely"}[urgency]
    return (f'<div class="rw-sum"><div class="big">{esc(name)} needs a {esc(test.lower())} {when}, '
            f'by {esc(due)}.</div><dl><dt>Test</dt><dd>{esc(test)}</dd><dt>Due by</dt><dd>{esc(due)}</dd>'
            f'<dt>Urgency</dt><dd>{esc(urgency)}</dd><dt>Where</dt><dd>{esc(trust)}</dd>'
            f'<dt>AI confidence</dt><dd>{confidence:.0%}</dd><dt>Status</dt><dd>{esc(review_state.replace("_", " "))}</dd>'
            f'<dt>Because the report says</dt><dd>&ldquo;{esc(evidence)}&rdquo;</dd></dl></div>')
