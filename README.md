# Resultwise

**No follow-up silently lost.** Resultwise uses AI to read radiology, echo and bone-density reports, turns every
recommended follow-up into a tracked task, checks every hospital for a booking, escalates when nothing happens,
and sends a clinician-approved message the patient can read in their own language, in easy read, larger text or
high contrast, or have read aloud.

Breast cancer focus: indeterminate imaging, heart scans during HER2 treatment, bone density scans on aromatase
inhibitors, surveillance mammograms, and incidental findings on staging CT.

> Hackathon MVP. **All data is synthetic.** Fictional trusts, invented patients and clinicians, NHS numbers from
> the 999 test range, fake phone numbers (Ofcom 01632 960xxx). Not a medical device, not clinically validated.

## The problem

Scan reports often end with a recommendation such as *"repeat echocardiogram in 12 weeks"* or *"core biopsy
advised"*. It's free text, so someone has to read it, order the test, book it and tell the patient. That chain
breaks, especially when care moves between hospitals and GPs on different record systems, and each system only
sees its own bookings. The patient finds out late.

Breast cancer patients are especially exposed: many scheduled scans over years, often across several organisations.

## Problem statement

> **How might we make sure that every follow-up recommended in a breast cancer patient's imaging report is
> completed on time, even when her care spans several NHS organisations and record systems, without adding to
> clinicians' workload, and without leaving behind patients who are older, don't speak English, or don't use
> digital services?**

Full problem statement, evidence, success measures and scope: [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md).

## Our solution

Resultwise **follows the patient, not the hospital**. AI reads and drafts. Plain rules do the tracking.
Clinicians make every decision. Patients can reply.

```
report ──► Claude reads it ──► Pydantic schema check ──► evidence quote must exist in report ──► confidence check
                                   (any failure → human review, never dropped)
       ──► task (SQLite) ──► daily rules: booked at ANY trust? due soon? overdue? 14+ days overdue?
                                   └► clinician alert → nurse outreach; urgent findings → phone call, never a message
       ──► message drafted ──► Claude translates + back-translates ──► date/phone/name fact check ──► clinician approves
       ──► patient portal: any of 18 languages, easy read, text size, high contrast, read aloud, reply buttons
       ──► patient replies ──► clinician worklist          every step ──► audit log          tasks ──► FHIR Task export
```

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # optional; Windows: set ANTHROPIC_API_KEY=...
streamlit run app.py
```

## Turn on the AI (Claude API)

- **Locally:** set `ANTHROPIC_API_KEY` as above, or paste it under *Settings* in the sidebar (kept in that browser
  session only).
- **Streamlit Community Cloud:** app → *Settings* → *Secrets*, and paste:
  ```toml
  ANTHROPIC_API_KEY = "sk-ant-..."
  ```
  The app restarts and the sidebar shows **AI on: claude-sonnet-5-5**.

Models: `claude-sonnet-5-5` reads reports; `claude-haiku-5-5` translates, back-translates and writes easy read.
Override with `RESULTWISE_CLAUDE_MODEL` / `RESULTWISE_CLAUDE_FAST_MODEL`. OpenAI also works (`OPENAI_API_KEY`).

**Without a key** Resultwise uses transparent offline rules and pre-written Polish, Urdu and Tamil templates, so
the demo never fails on stage Wi-Fi. If an AI call fails, it falls back to offline and flags the task for human review.

Only synthetic text is ever sent to the API. Real patient data would need a contract, DPIA and IG approval first.

## What's in the app

**Clinician (sidebar: I am → Clinician)**

| View | What it shows |
|---|---|
| Worklist | The loop strip (every follow-up from closed to overdue), priority cards, urgent *Phone patient* tags, patient replies, messages to approve, CSV export |
| Task panel | The full report with the AI's evidence sentence highlighted, who can see this follow-up at each hospital, confirm / correct / dismiss with reason, preview the patient message in any language, export as FHIR Task |
| Patient journey | Two-hospital swimlanes: Northbridge's record, Valeford's record, Resultwise |
| Report inbox | New reports, *Re-read all reports with Claude* (parallel), paste-your-own report |
| Equity | Past on-time rates by age, language, deprivation, plus current tasks by group |
| Evaluation | Recall, precision, urgent recall, timeframe and urgency accuracy, on development and held-out reports |
| Audit log | Every AI output, rule decision, patient reply and human action |

**Patient (sidebar: I am → Patient)**

Only their own approved messages: choose any of 18 languages, easy read, text size, high contrast, read aloud
(uses the device's voices), and reply: *I've already booked it*, *Please call me*, *I can't make it*,
*I don't understand*. Replies appear on the clinician worklist.

## Synthetic data

`python data/generate_data.py` regenerates everything (fixed random seed):

| File | Contents |
|---|---|
| `data/reports.json` | **104 full NHS-style reports** with gold labels: header (trust, patient, NHS test number, DOB), examination, accession, referrer, clinical indication, comparison, technique, findings, conclusion, reporter. 28 hand-written story reports + 76 generated from 17 clinical scenarios with varied phrasing (formal, abbreviated, hedged, buried in findings, negated) |
| `data/heldout_reports.json` | 10 reports written after the offline rules, never used to tune them |
| `data/patients.csv` | 60 patients: age, sex, language (English, Polish, Urdu, Tamil, Bengali, Punjabi, Romanian, Somali), contact channel, deprivation quintile, home trust |
| `data/bookings.csv` | Bookings across two trusts; some deliberately missing (booking chance lower for older, non-English and deprived patients) |
| `data/history.csv` | 900 past follow-ups with outcomes, for the equity view |

## 4-minute demo script

Start with *Settings → Reset demo* (simulated date Sun 25 Oct 2026).

1. **Worklist (20s).** The loop strip: 92 follow-ups tracked. "Doreen, 84, missed her mammogram; it's escalated."
2. **Report inbox (40s).** *Read all 3 new reports*: suspicious findings get a red *Phone patient* tag. Then paste a
   report with unusual wording ("would suggest a further scan in about a month") and show Claude extracting it,
   with the evidence sentence.
3. **Patient journey, Halina Nowak (40s).** Northbridge: *handed over*. Valeford: *no record*. Click **+2 wk**:
   Resultwise turns **Overdue**. "This is the gap no single hospital's record can see."
4. **Worklist, translation safety (40s).** *Settings → Simulate a translation error*, *Regenerate* Halina's Polish
   message: **Blocked**, the date changed. Turn it off, *Regenerate*, *Approve and send*.
5. **Patient (50s).** Switch *I am → Patient*, sign in as Halina. Polish message; switch to Urdu or Bengali (Claude
   translates live), *Easy read*, *Extra large*, *High contrast*, *Read aloud*. Tap *Please call me*.
6. **Back to Clinician (15s).** The reply is on the worklist. Every step is in the audit log.
7. **Equity + Evaluation (25s).** Who is being missed; held-out accuracy offline vs Claude.

## Tests

```bash
pip install pytest
pytest -q          # 27 tests: extraction, schema validation, mocked Claude path (hallucination check,
                   # bad JSON fallback, no temperature), cross-trust tracking, escalation, urgent never messaged,
                   # translation fact check, easy read, patient replies, FHIR export, report format
python eval.py --engine offline    # or: --engine claude
```

Tests and the offline evaluation run on every push (GitHub Actions).

## Files

```
PROBLEM_STATEMENT.md       problem, evidence, statement, success measures, scope
DEVPOST.md                 Devpost submission text
app.py                     Streamlit app (clinician + patient)
eval.py                    command-line evaluation
resultwise/extract.py      Claude / offline extraction + safety checks
resultwise/llm.py          Claude / OpenAI client (standard library only)
resultwise/messages.py     drafting, translation, back-translation, fact check, easy read, languages
resultwise/rules.py        tracking engine, escalation, cross-trust views
resultwise/pipeline.py     processing (parallel re-read), clinician actions, patient replies, demo seed
resultwise/fhir.py         FHIR R4 Task export
resultwise/ui.py           visual components (loop strip, cards, swimlanes, portal, read aloud)
data/                      synthetic data + generators
tests/                     pytest suite
```

## Honest limits

- Synthetic data only. Offline rules score 97% recall on the development reports they were tuned on, but 22% on
  held-out reports; that gap is why the AI reads the reports. Run `python eval.py --engine claude` for Claude's numbers.
- Offline translations (Polish, Urdu, Tamil) are demo templates; AI translations are fact-checked but would still
  need professional review before real use. Read aloud depends on the voices installed on the patient's device.
- Bookings are simulated; a real system would read orders from each trust's record system via FHIR / HL7.
- Real deployment needs a DPIA, Caldicott and DCB0129/0160 clinical safety work, data-sharing agreements,
  UK-hosted infrastructure, and validation on real reports.
