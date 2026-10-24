# Resultwise

**No follow-up silently lost.** Resultwise reads radiology, echo and DXA reports, turns each recommended
follow-up into a tracked task, checks every trust for a booking, escalates when nothing happens, and drafts a
clinician-approved patient message in the patient's own language.

Breast cancer focus: indeterminate imaging, heart scans during HER2 treatment, bone density scans on aromatase
inhibitors, and surveillance mammograms.

> Hackathon prototype. **All data is synthetic.** Fictional trusts, invented patients, fake phone numbers
> (Ofcom 01632 960xxx drama range). Not a medical device, not clinically validated.

## The problem

Scan reports often end with a recommendation such as *"repeat echocardiogram in 12 weeks"* or *"core biopsy
advised"*. It's free text, so someone has to read it, order the test, book it and tell the patient. That chain
breaks, especially when care moves between hospitals and GPs on different record systems, and each system only
sees its own bookings. The patient finds out late.

Breast cancer patients are especially exposed: they have many scheduled scans over years (indeterminate imaging,
3-monthly heart scans on HER2 drugs, bone density scans on aromatase inhibitors, yearly surveillance mammograms),
often across several organisations.

## Problem statement

> **How might we make sure that every follow-up recommended in a breast cancer patient's imaging report is
> completed on time, even when her care spans several NHS organisations and record systems, without adding to
> clinicians' workload, and without leaving behind patients who are older, don't speak English, or don't use
> digital services?**

Full problem statement, evidence, success measures and scope: [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md).

## Our solution

Resultwise **follows the patient, not the hospital**. AI only reads and drafts. Plain rules do the tracking.
Clinicians make every decision.

## Run it (about 2 minutes)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

It opens in your browser. No API key or internet needed: the default **Offline** engine works on its own,
so the demo cannot fail on stage Wi-Fi.

**Optional AI engine:** choose Claude or OpenAI in the sidebar and paste a key (kept in the session only), or
set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` before starting. If the call fails, Resultwise falls back to offline
extraction and flags every task for human review. It never drops a task.

**Reset any time** with the sidebar's *Reset demo* button (or delete `resultwise.db`).

## What's in the app

| View | What it shows |
|---|---|
| Clinician worklist | Priority-sorted tasks, urgent "phone the patient" flags, AI evidence quote, confirm / correct / dismiss (reason required), messages awaiting approval |
| Patient journey (two trusts) | What Northbridge's system sees, what Valeford's system sees, and what Resultwise sees for the same patient |
| Report inbox | New reports to process, plus a box to paste any synthetic report and watch extraction live |
| Patient view | The approved message as the patient gets it (app, letter, carer or phone script), English / translated toggle |
| Equity | On-time follow-up rate by age, language and deprivation (synthetic history with a deliberate disparity) |
| Evaluation | Recall, precision, urgent recall, timeframe and urgency accuracy, on development and held-out reports |
| Audit log | Every AI output, rule decision and human action |

Sidebar: simulated date, **+1 / +2 / +4 week** buttons, engine choice, and *Simulate a translation error*.

## 3-minute demo script

Start after *Reset demo* (simulated date Sun 25 Oct 2026).

1. **Worklist (20s).** "Doreen, 84, missed her annual mammogram 15 days ago. It's escalated to nurse outreach and a
   message to her carer is waiting for approval."
2. **Report inbox (20s).** Click *Process all 3 new reports*. Back on the worklist, suspicious findings show
   **Urgent: phone patient**. "Urgent results never get an automated message. A clinician calls."
3. **Patient journey, Halina Nowak (40s).** Her echo during HER2 treatment was recommended at Northbridge, to be
   done at Valeford. Northbridge: *handed over, not tracked*. Valeford: *no record of this request*.
   Resultwise: *due soon*. Click **+2 wk**: Resultwise turns **Overdue · clinician alerted**. Both hospitals'
   own systems still see nothing wrong. "This is the gap Epic can't see on its own."
4. **Worklist, translation safety (40s).** Turn on *Simulate a translation error*, click *Regenerate* on Halina's
   Polish message: **BLOCKED**, the date changed in translation. Turn it off, *Regenerate*, check passes,
   *Approve and send*.
5. **Patient view (15s).** Halina's message in Polish, toggle to English. No diagnosis in the text.
6. **Patient journey, Susan Whitaker (15s).** Click **+2 wk** again. Northbridge's own system now says OVERDUE,
   a false alarm, because she moved and booked at Valeford. Resultwise sees the Valeford booking: no duplicate scan.
7. **Equity (15s).** "Patients over 80, non-English speakers and the most deprived areas miss more follow-ups.
   Resultwise shows where to change outreach."
8. **Evaluation (15s).** Held-out set: hand-written rules catch only 22% of follow-ups they've never seen. That's
   why the extraction step needs an LLM, and why every output is validated and audited.

## How it works

```
report ──► AI extraction (LLM or offline rules)
             └► Pydantic schema validation ─► evidence-quote check ─► confidence check
                    (fail → human review, never dropped)
         ──► SQLite task ──► rules engine (daily): booked at ANY trust? due soon? overdue? 14+ days?
                                 └► escalate: clinician alert → nurse outreach
         ──► message drafter ─► translation ─► fact check (date, phone, name) ─► clinician approves ─► sent
         ──► audit log for every step
```

AI only reads and drafts. Plain rules do the tracking. Clinicians make every decision.

## Tests

```bash
pip install pytest
pytest -q          # 20 tests: extraction, schema validation, AI fallback, cross-trust tracking,
                   # escalation, urgent-never-messaged, translation fact check, audit
python eval.py     # accuracy on development and held-out reports
```

Tests and the evaluation also run automatically on every push (GitHub Actions).

## Files

```
PROBLEM_STATEMENT.md       problem, evidence, statement, success measures, scope
DEVPOST.md                 Devpost submission text
app.py                     Streamlit app
eval.py                    command-line evaluation (writes eval_results.json)
resultwise/schema.py       Pydantic contracts for AI output
resultwise/extract.py      offline + LLM extraction, safety checks
resultwise/llm.py          tiny Claude / OpenAI client (standard library only)
resultwise/rules.py        tracking engine, escalation, cross-trust views
resultwise/messages.py     message templates, translation, fact check
resultwise/pipeline.py     processing, clinician actions, demo seed
resultwise/db.py           SQLite schema
data/generate_data.py      regenerates every synthetic data file
data/reports.json          28 labelled development reports
data/heldout_reports.json  10 held-out reports (never used to tune the rules)
tests/                     pytest safety tests
```

## Honest limits

- Synthetic data only; offline rules were tuned on the development reports (100% there, 22% recall held-out).
- LLM mode is wired up but was not run during build (no key in the build environment). Test it with your key
  before the demo: `python eval.py --engine claude`.
- Offline translations (Polish, Urdu, Tamil) are demo templates and must be professionally translated before
  any real use.
- Bookings are simulated; a real system would read orders from each trust's record system via FHIR / HL7.
- Real deployment needs DPIA, Caldicott and DCB0129/0160 clinical safety work, data-sharing agreements and
  validation on real reports.
