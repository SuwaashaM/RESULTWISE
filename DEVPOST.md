# RESULTWISE

**Tagline:** Reads breast cancer scan reports with AI, tracks every recommended follow-up across hospitals, and reaches the patient in her own language, with a clinician approving every step.

---

## Inspiration

### It starts with a wait

Halina is 61. She's being treated for HER2-positive breast cancer, and the drug that's saving her life can quietly
damage her heart. So every three months she has a heart scan.

Her latest report, written at Northbridge Hospital, ends with one line:

> *"Repeat echocardiogram in 12 weeks; this will be performed at Valeford Hospitals."*

Then the waiting starts. Northbridge thinks the job has been handed over. Valeford has no record of it. Halina
assumes no news is good news. Twelve weeks pass. Then fourteen. Nobody books the scan, and nobody notices, because
**no single system can see the whole journey**.

### We checked whether this is real

It is.

- The UK's Healthcare Safety Investigation Branch investigated **failures to communicate and follow up significant
  radiology findings**, including a woman whose possible lung cancer on an X-ray wasn't acted on. They found practice
  varies widely, there's little assurance that recommended actions happen, and many trusts' IT can't confirm that
  follow-up was completed.
- A US study of 539 CT reports found radiologists' follow-up recommendations were acted on **only 39% of the time**,
  rising to **57%** when the patient's GP worked in the same organisation. **Crossing an organisational boundary
  makes it worse.**
- Breast cancer patients cross those boundaries constantly: years of scheduled checks (heart scans during HER2
  treatment, bone density scans on hormone tablets, yearly mammograms, follow-up of unclear findings), often at
  different hospitals.

### Then we found Epic, and the exact gap

Big hospitals already tackle this. Northwestern Medicine in the US uses AI to read imaging reports and flag
findings, alerts doctors through its **Epic** record system, and has nurses chase anything not followed up. It works.

But it works **inside one organisation's record**. The NHS is a patchwork of record systems, and Halina's
follow-up wasn't lost inside a hospital. It was lost **between two of them**. That's the gap we set out to close:
a safety net that **follows the patient, not the hospital**.

### And we realised the most important part is human

The easy version of this project is "AI reads the report and messages the patient". We decided that would be
dangerous. A scan report can carry life-changing news. AI can't judge what's too sensitive to send by text, or
whether a patient should hear something from a person first. So in Resultwise **the AI is an assistant, never the
decision-maker**. It reads and translates; a clinician checks everything before it reaches a patient.

That matched the message of the hackathon's opening talk: healthcare needs **Artificial Limited Intelligence**:
AI limited enough to be regulated, safety-checked, version-controlled and trusted, rather than chasing
"super-intelligence". We built Resultwise to be exactly that.

---

## What it does

Resultwise closes the loop in five steps:

1. **Report arrives.** A clinician pastes or uploads a scan report (`.txt`, `.pdf` or `.docx`).
2. **AI reads it.** It extracts every follow-up: the test, due date, urgency, a confidence score, and **the exact
   sentence it came from**, highlighted in the report. If that sentence isn't really in the report, or the AI is
   unsure, the case is flagged for a careful human check.
3. **Clinician checks.** Nothing is tracked until a clinician ticks *"I have checked this against the report"*
   and confirms, or corrects it. Every correction is logged.
4. **Tracker watches.** Plain rules, not AI, check **every hospital** for a booking. Due soon → reminder drafted.
   Overdue → clinician alert. 14 days overdue → nurse outreach. Booked at the other hospital → loop closed, no
   false alarm.
5. **Patient is reached.** A plain-language message names only the test and how to book, **never a diagnosis**.
   The AI translates it and back-translates it, and a fact check blocks any translation that changes the date,
   phone number or name. **A clinician approves before anything is sent.** Urgent findings never get an automated
   message: **a clinician phones.**

**For the patient:** a portal in 8 languages (including right-to-left Urdu and Arabic), with the clinician-approved
original shown side by side, easy read, large text, high contrast and read aloud. Carers can receive messages, and
patients without the app get a text message.

**Patients can talk back.** They can tap *"I've already booked it"*, *"Please call me"*, *"I can't make it"* or
*"I don't understand"*, or **ask a question in their own words, in any language**. The AI translates it and sorts
it; anything serious (a new symptom, worry about results) appears on the clinician's screen **in red within
seconds**, and the patient instantly sees a fixed safety message: call 999, or 111 for urgent advice. **The AI
drafts a reply, but only a clinician can send it.**

Every AI output, rule decision and human action goes into an **audit log**, and every follow-up can be exported as
a **FHIR R4 Task**, the standard format other hospital systems can read.

---

## How we built it

**Architecture** (diagram and plain-English explanation of each layer in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)):

| Layer | What | Built with |
|---|---|---|
| People | Clinician workspace + patient portal, works on phone, tablet and laptop | React, TanStack Start, Tailwind, shadcn/ui |
| Server | AI functions (read, translate, sort questions) and tracking rules | TanStack Start server functions, TypeScript |
| Safety | Fixed answer formats, exact-sentence check, confidence threshold, translation fact check, serious-by-default triage, urgent → phone | Zod, rule code, 60+ tests |
| AI model | Reads and translates only, never decides | Lovable AI gateway (OpenAI model); Gemini in our Python prototype |
| Data | Live database: a patient's reply reaches the clinician in about a second | Lovable Cloud (Supabase Postgres + Realtime) |
| Out | FHIR R4 Task export, audit log | FHIR R4 |

**We followed the 1 → 2 → FREE idea from the opening talk:**

- **Step 1: explore with a powerful model.** In a Python test bench (Streamlit, Pydantic, SQLite) we used a large
  language model (Gemini) to read reports. On **10 held-out reports it had never seen**, it found **100%** of
  follow-ups (90% precision) and **every urgent one**.
- **Step 2: compare with something simple, free and explainable.** We built transparent keyword rules that run
  offline at no cost. They scored 97% on the reports we tuned them on, but **only 22% on the held-out reports**.
  That honest gap told us exactly where the AI earns its place, and the rules stay as a fallback so the system
  never silently fails.
- **FREE(ZE): freeze it so it can be checked.** Fixed answer formats, a version-controlled evaluation harness
  (`eval.py`), 90+ automated tests across both codebases and CI on every push mean any change to the AI can be
  re-tested against the same benchmark.

**What we're proud of technically:** the exact-sentence check that catches made-up answers; urgent findings
hard-wired to a phone call; translation fact checks with back-translation; live sync between two devices; and
**104 full NHS-style synthetic reports with correct answers attached**, written in deliberately tricky styles
(shorthand, hedged, hidden in the findings, negated).

---

## Challenges we ran into

- **Being honest about accuracy.** Our rules looked brilliant (97%) until we tested them on reports written
  afterwards (22%). It would have been easy to report the first number. We report both, because a score on data
  you tuned against means nothing.
- **Deciding what the AI should *not* do.** Every time we made the AI do more, the system got harder to trust. We
  kept due dates, escalation and channel choice as plain rules, and kept every patient-facing decision with a human.
- **Sensitive information.** AI can't tell when a message is too sensitive to send. So messages never mention a
  finding, urgent results always go to a phone call, and nothing reaches a patient without clinician approval.
- **Safe translation.** Machine translation can silently change a date or phone number. We built a fact check that
  blocks it, and show the clinician a back-translation before they approve.
- **No real data, by design.** We had to build a realistic world from scratch: two fictional hospitals, 60 patients,
  bookings with realistic gaps, and reports varied enough to genuinely test the AI.

## Accomplishments that we're proud of

- A complete, working loop: report → AI reads it → clinician confirms → rules track across hospitals → translated,
  fact-checked, approved message → patient replies → back to the clinician.
- The **two-hospital view** that makes the gap visible: Northbridge says *handed over*, Valeford says *no record*,
  Resultwise says *overdue, escalated*.
- Patients who are usually left behind (older, not fluent in English, without a smartphone, or relying on a carer)
  are designed in from the start, not added at the end.
- An **equity view** that checks who is being missed by age, language and deprivation.
- Zero real patient data, and an honest evaluation including our weak spots.

## What we learned

- **Follow-ups rarely get lost inside one hospital. They get lost at the handover between hospitals.**
- **Human review is the feature, not the bottleneck.** AI is best as an assistant that reads faster than a person
  but never decides for one.
- **Privacy is a design decision, not an add-on.** We learned how health data must be handled (lawful basis,
  data protection impact assessments, Caldicott principles, data-sharing agreements) and designed so that only
  synthetic text ever reaches an AI API, and patients only ever see clinician-approved words.
- **Recall is the safety metric; precision decides trust.** Missing a follow-up is dangerous; too many false alarms
  and clinicians stop listening.
- **Limited, testable AI beats impressive, unexplainable AI** for healthcare: cheaper, safer and possible to regulate.

## What's next for RESULTWISE

With another week:

1. **Finish 1 → 2 → FREE.** Replace the cloud model with a **small open-source model running locally**, benchmark
   it against our step-1 results on the same evaluation set, then freeze it, so it's free to run and patient data
   never leaves the hospital.
2. **A bigger, harder test set**, reviewed by a breast-imaging clinician, and validation on de-identified real
   reports under proper approvals.
3. **Connect to real record systems** through FHIR / HL7, to read real orders and bookings from each hospital.
4. **Clinical safety and governance:** DCB0129/0160 safety case, data protection impact assessment, information
   governance review with an NHS trust partner.
5. **Co-design with patients and carers**, and professionally checked translations.
6. **Pilot one checkpoint first:** heart monitoring during HER2 treatment, where the schedule is clear and a miss
   is costly.

---

## Built with

typescript · react · tanstack-start · tailwindcss · shadcn-ui · lovable · lovable-cloud · supabase · postgresql ·
zod · lovable-ai-gateway · openai · python · streamlit · pydantic · sqlite · pandas · google-gemini · fhir ·
web-speech-api · github-actions · mermaid · synthetic-data

## Data, privacy, consent and bias (summary)

- **Synthetic data only.** No real patient data at any stage. Fictional hospitals and people, NHS numbers from the
  999 test range, phone numbers from Ofcom's drama ranges. Full dataset and data dictionary in [`data/`](data/README.md).
- **Privacy:** only synthetic text is ever sent to an AI API; keys stay server-side; messages never reveal a finding.
- **Consent:** patients choose their contact method (app, text, carer, phone); nothing AI-written reaches them
  without clinician approval; they can reply or say *"I don't understand"* at any time.
- **Bias:** we built known inequalities into the synthetic history (older, non-English-speaking and more deprived
  patients are less likely to be followed up on time) to test that the equity view catches them, and report our
  evaluation limits openly.

## Honest limits

All data is synthetic. Not a medical device and not clinically validated. The held-out test set is small (10
reports) and written by our team. Bookings are simulated; cross-hospital tracking is shown in simulation.
Translations should be checked by native speakers before real use.

**Sources:** [HSSIB investigation](https://hssib.org.uk/patient-safety-investigations/failures-in-communication-or-follow-up-of-unexpected-significant-radiological-findings) ·
[Hansra et al., JACR 2020, via Radiology Business](https://radiologybusiness.com/topics/health-it/enterprise-imaging/primary-care-outpatient-providers-radiologist-incidental-findings) ·
[Northwestern Medicine: AI and imaging follow-up](https://physicianforum.nm.org/learn-more-about-how-ai-supports-imaging.html)
