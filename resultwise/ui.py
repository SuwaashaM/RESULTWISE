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
