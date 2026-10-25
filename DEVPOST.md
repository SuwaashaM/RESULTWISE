# ResultWise

**Tagline:** Reads breast cancer scan reports with AI, tracks every recommended follow-up across hospitals, and reaches the patient in her own language, with a clinician approving every step.

## Inspiration

Halina is 61 and on trastuzumab for HER2-positive breast cancer. The drug can damage her heart, so she has a heart
scan every three months. Her latest report from Northbridge ends with one line: *"Repeat echocardiogram in 12
weeks; this will be performed at Valeford Hospitals."*

Northbridge thinks it has handed over. Valeford has no record. Halina assumes no news is good news. Twelve weeks
pass, then fourteen, and nobody notices, because no single system sees the whole journey.

We wanted to know if this really happens. It does. The UK's Healthcare Safety Investigation Branch found that
significant radiology findings are not reliably followed up and that many trusts' IT can't confirm the follow-up
happened. A US study of 539 CT reports found recommendations were acted on only 39% of the time, rising to 57%
when the GP was in the same organisation. Crossing a boundary makes it worse, and breast cancer patients cross
them for years: heart scans, bone density scans, mammograms, often at different hospitals.

Then we looked at how big systems solve it. Northwestern Medicine uses AI to read imaging reports and flags
follow-ups inside its Epic record, with nurses chasing anything missed. It works, but only inside one
organisation. Halina's follow-up wasn't lost inside a hospital. It was lost between two. That's our gap.

We also decided early that the AI should assist, not decide. A report can carry life-changing news, and AI can't
judge what is too sensitive to send. The opening talk's idea of *Artificial Limited Intelligence* (AI limited
enough to be tested, regulated and trusted, not a race to AGI) is exactly how we built ResultWise.

## What it does

1. **Reads the report.** Paste or upload a report (.txt, .pdf, .docx). The AI pulls out each follow-up: test, due
   date, urgency, confidence, and the exact sentence it came from, highlighted. If that sentence isn't in the report
   or the AI is unsure, the case is flagged for a careful check.
2. **Clinician confirms.** Nothing is tracked until a clinician ticks "I have checked this against the report".
   Corrections are logged.
3. **Tracks across hospitals.** Plain rules, not AI, check both hospitals for a booking. Due soon: reminder drafted.
   Overdue: clinician alert. 14 days overdue: nurse outreach. Booked elsewhere: loop closed, no false alarm.
4. **Reaches the patient.** The message names only the test and how to book, never a finding. The AI translates
   and back-translates it, a fact check blocks any changed date, phone number or name, and a clinician approves it
   before sending. Urgent findings are never messaged; a clinician phones.
5. **Lets the patient reply.** The patient portal works in 8 languages, with easy read, large text, high contrast
   and read aloud, plus carers and text messages for people without the app. Patients can tap a reply or ask a
   question in their own language. The AI translates and sorts it. Serious questions reach the clinician in red
   within seconds, and the patient instantly gets fixed safety advice (999 / 111). Only a clinician can send a reply.

Every AI output and human action is logged, and each follow-up exports as a FHIR R4 Task.

## How we built it

- **Web app:** React and TanStack Start, built with Lovable. Lovable Cloud (Supabase Postgres + Realtime) for live
  sync, so a patient's reply appears on the clinician's screen in about a second.
- **AI:** server-side calls through Lovable's AI gateway (an OpenAI model), forced into a fixed format with Zod.
  The AI only reads, translates and sorts.
- **Safety layer:** exact-sentence check, confidence threshold, translation fact check, serious-by-default
  question triage, urgent cases hard-wired to a phone call.
- **Python test bench:** Streamlit, Pydantic and SQLite, with Gemini, to build and measure the AI.
- **Synthetic data:** 104 NHS-style breast cancer reports with correct answers, written in tricky styles
  (shorthand, hedged, hidden in the findings, negated), plus 60 patients and 900 past follow-ups.
- **Architecture:** diagram in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

We followed the opening talk's **1 → 2 → FREE** method:

- **Step 1:** a powerful model. On 10 held-out reports it had never seen, Gemini found 100% of follow-ups
  (90% precision) and every urgent one.
- **Step 2:** a simple, free, explainable baseline. Our keyword rules scored 97% on reports we tuned them on, but
  only 22% on the held-out set. That told us exactly where AI earns its place. The rules stay as a fallback.
- **FREE(ZE):** fixed formats, an evaluation script and 90+ automated tests across both codebases, so any change
  can be re-checked against the same benchmark.

## Challenges we ran into

- **Honest accuracy.** 97% looked great until we tested on new reports and got 22%. We report both.
- **Keeping the AI limited.** Every extra job we gave the AI made the system harder to trust, so tracking,
  escalation and every patient-facing decision stay with rules and people.
- **Sensitive information.** Messages never mention a finding, urgent results go to a phone call, and nothing
  reaches a patient without approval.
- **Safe translation.** Translation can quietly change a date. We block that and show the clinician a
  back-translation first.
- **No real data.** We had to build a believable world from scratch: two hospitals, patients, missing bookings,
  and reports varied enough to actually test the AI.

## Accomplishments that we're proud of

- A full working loop from report to patient reply and back, live across two devices.
- The two-hospital view: Northbridge says "handed over", Valeford says "no record", ResultWise says "overdue".
- Designing for the patients most often missed: older people, non-English speakers, people without smartphones,
  and carers.
- Zero real patient data, and an evaluation that shows our weak spots as well as our strengths.

## What we learned

- Follow-ups rarely get lost inside a hospital. They get lost at the handover.
- Human review isn't a bottleneck. It's what makes the AI safe to use.
- Privacy has to be designed in: lawful basis, DPIAs, Caldicott principles, data-sharing agreements. We kept real
  data out entirely and only ever sent synthetic text to an AI.
- Recall keeps patients safe; precision keeps clinicians listening.
- In healthcare, limited AI you can test beats impressive AI you can't explain.

## What's next for ResultWise

- **Finish 1 → 2 → FREE:** swap the cloud model for a small open-source model running locally, benchmark it
  against step 1, and freeze it, so it's free to run and data never leaves the hospital.
- A larger test set reviewed by a breast-imaging clinician, then validation on de-identified real reports.
- Connect to real record systems through FHIR / HL7.
- Clinical safety case (DCB0129/0160), DPIA and information governance with an NHS trust.
- Co-design with patients and carers; professionally checked translations.
- Pilot one checkpoint first: heart monitoring during HER2 treatment.

## Built with

typescript · react · tanstack-start · tailwindcss · shadcn-ui · lovable · lovable-cloud · supabase · postgresql ·
zod · lovable-ai-gateway · openai · python · streamlit · pydantic · sqlite · pandas · google-gemini · fhir ·
web-speech-api · github-actions · synthetic-data

## Data, privacy and limits

All data is synthetic: fictional hospitals and people, NHS numbers from the 999 test range, phone numbers from
Ofcom's drama ranges ([`data/README.md`](data/README.md)). Only synthetic text is sent to an AI, keys stay
server-side, and patients only see clinician-approved words. We built known inequalities into the synthetic history
to check the equity view catches them. Not a medical device and not clinically validated. The held-out test set is
small, and translations need native-speaker review before real use.

**Sources:** [HSSIB investigation](https://hssib.org.uk/patient-safety-investigations/failures-in-communication-or-follow-up-of-unexpected-significant-radiological-findings) ·
[Hansra et al., JACR 2020](https://radiologybusiness.com/topics/health-it/enterprise-imaging/primary-care-outpatient-providers-radiologist-incidental-findings) ·
[Northwestern Medicine](https://physicianforum.nm.org/learn-more-about-how-ai-supports-imaging.html)
