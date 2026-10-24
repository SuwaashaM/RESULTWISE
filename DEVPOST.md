# Resultwise

**Tagline:** No follow-up silently lost: an AI safety net that tracks scan recommendations across hospitals, GPs and systems.

## Inspiration

A radiologist writes "repeat echo in 12 weeks". Then the report goes to a busy inbox, the patient's care moves
between hospitals, and nobody owns the next step. Studies of incidental findings show large shares of
recommended follow-ups never happen, and the patient finds out late.

Northwestern Medicine in the US showed the fix works: an AI that reads reports and tracks follow-ups inside
their Epic record. But the NHS is fragmented. A breast cancer patient may have surgery at one trust, heart scans
at another, and survivorship care with her GP, on different record systems. Each system sees only its own part.
We wanted a safety net that follows the **patient**, not the hospital.

## What it does

Resultwise focuses on the breast cancer pathway, where patients have many scheduled scans over years:
indeterminate imaging, heart scans every ~3 months during HER2 treatment, bone density scans on aromatase
inhibitors, and yearly surveillance mammograms.

1. **Reads** each report and turns recommendations into structured tasks (test, due date, urgency, evidence quote).
2. **Validates** every AI output: schema check, the evidence quote must appear in the report, low confidence goes
   to a human. Nothing is silently dropped.
3. **Tracks** each task daily, checking for a booking at **any** trust.
4. **Escalates** when nothing is booked: clinician alert, then nurse outreach.
5. **Drafts a patient message** in plain language and the patient's preferred language. A fact check blocks any
   translation that changes the date or phone number, and a clinician approves before anything is sent.
   Urgent findings never get an automated message: a clinician phones.
6. **Shows equity gaps:** on-time follow-up by age, language and deprivation, so trusts can see who they're failing to reach.
7. **Audits** every AI output, rule decision and human action.

**Demo moment:** Halina's echo was recommended at one trust, to be done at another. Hospital A's system says
"handed over". Hospital B's says "no record". Resultwise flags it overdue, drafts a Polish message, and blocks a
deliberately broken translation before it reaches her.

## How we built it

- **Python + Streamlit** for the clinician worklist, cross-trust journey, patient view, equity and evaluation screens.
- **LLM extraction** (Claude or OpenAI) with a strict JSON prompt, plus a transparent **offline rule-based engine**
  so the demo runs with no key or internet.
- **Pydantic** contracts reject malformed AI output; an evidence-quote check catches hallucinated follow-ups.
- **SQLite** for tasks, bookings, messages and the audit log; a **deterministic rules engine** for tracking and
  escalation, with a simulated clock to show weeks passing live.
- **Synthetic data:** 38 labelled reports, 24 patients, bookings across two fictional trusts, and 900 historical
  follow-ups for the equity view. No real patient data anywhere.

## Challenges we ran into

- **Honest evaluation.** Our offline rules scored 100% on the reports we wrote them against, and 22% recall on
  10 held-out reports. That gap is the clearest argument for using an LLM, and for never trusting a score on
  data you tuned against.
- **Deciding what AI should not do.** We kept due dates, escalation and channel choice as plain rules, so they
  are predictable and auditable.
- **Safe multilingual messaging.** Machine translation can silently change a date. We built a fact check that
  blocks it and kept messages free of any diagnosis.

## Accomplishments we're proud of

- An end-to-end loop: report → task → tracking → escalation → translated, approved message → audit.
- The cross-trust view that makes the "Epic can't see between hospitals" point concrete.
- Safety designed in: human in the loop, urgent findings to a phone call, nothing dropped on AI failure.

## What we learned

- Most follow-ups don't get lost inside one hospital. They get lost at handovers.
- Sensitivity is the safety metric, but precision decides whether clinicians trust the alerts.
- Older, non-English-speaking and deprived patients need different channels, not just an app.

## What's next

- Run and report the LLM engine on a larger labelled set, ideally de-identified UK reports under proper approvals.
- Connect to record systems through **FHIR / HL7** to read real orders and bookings.
- Clinical safety case (DCB0129/0160), DPIA and information-governance review with an NHS trust partner.
- Professionally translated templates and co-design with patients and carers.
- A small pilot on one breast pathway checkpoint (e.g. HER2 cardiac monitoring).

## Built with

python · streamlit · pydantic · sqlite · pandas · altair · claude-api · openai-api

## Honest limits

All data is synthetic. Not a medical device and not clinically validated. Bookings are simulated. Offline
translations are demo templates. Cross-organisation tracking is the vision; the prototype shows it in simulation.
