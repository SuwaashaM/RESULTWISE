# Problem statement

## The problem

When a radiologist, cardiac physiologist or bone-density service writes a report, it often ends with a
recommendation: *"repeat echocardiogram in 12 weeks"*, *"core biopsy advised"*, *"repeat DXA in 2 years"*,
*"follow-up CT chest in 3 months"*.

That recommendation is **free text**. For it to happen, someone has to read it, order the test, book it,
tell the patient, and notice if it never takes place. In practice, that chain breaks often:

- The report goes to a clinician who has moved on, is on leave, or is overloaded.
- The recommendation is buried in the Findings section instead of the Conclusion.
- The patient's care moves between organisations: surgery at one trust, heart monitoring at another,
  long-term surveillance with the GP.
- Each organisation's record system only sees its own orders and bookings, so nobody sees the whole picture.
- No one person "owns" the follow-up, so when it doesn't happen, nothing alerts anyone.

The result is a **missed or delayed follow-up** that the patient often only discovers when a problem has grown:
a cancer recurrence found late, heart damage from cancer treatment that went unmonitored, or untreated bone
loss leading to fractures.

## Why breast cancer

Breast cancer patients have **many scheduled scans over many years**, often across several organisations:

| Checkpoint | Typical schedule | What a miss can mean |
|---|---|---|
| Indeterminate breast imaging (U3/R3/M3) | biopsy or short-interval recheck | delayed cancer diagnosis |
| Heart scans during HER2-targeted treatment | roughly every 3 months | treatment-related heart damage goes unnoticed |
| Bone density (DXA) on aromatase inhibitors | every 1–2 years | untreated osteoporosis and fractures |
| Surveillance mammograms after treatment | yearly, typically ~5 years | late detection of recurrence |

These are predictable, scheduled and safety-critical, which makes them a good fit for automated tracking.
Exact schedules vary by local protocol and should be checked against current NICE guidance (NG101).

## Who is affected

- **Patients**, especially those who are older, don't read English well, are digitally excluded, or live in
  deprived areas. They are more likely to miss follow-ups and less able to chase them.
- **Clinicians**, who rely on memory and scattered inboxes to keep track of results.
- **NHS trusts**, which carry the safety risk, serious incidents and complaints that follow a missed result.

## What already exists, and the gap

Northwestern Medicine (US) built an AI system inside its Epic record that reads radiology reports, alerts the
ordering physician and tracks follow-up to completion, and reported that more than 87% of identified findings
were followed up after go-live. Several NHS trusts now use Epic too.

But a system inside **one** record system can only see **one** organisation. The NHS remains a mix of record
systems (Epic, Oracle, Altera, MEDITECH, in-house systems and GP systems), and many follow-ups are lost
**at the handovers between them**. That gap is not covered by any single hospital's record.

## Problem statement

> **How might we make sure that every follow-up recommended in a breast cancer patient's imaging report is
> completed on time, even when her care spans several NHS organisations and record systems, without adding to
> clinicians' workload, and without leaving behind patients who are older, don't speak English, or don't use
> digital services?**

## Our answer: ResultWise

ResultWise is a follow-up safety net that **follows the patient, not the hospital**:

1. **AI reads** each report and turns recommendations into structured tasks (test, due date, urgency, evidence quote).
2. **Safety checks** validate every AI output; anything uncertain goes to a human. Nothing is silently dropped.
3. **Plain rules track** each task daily and check for a booking at **any** organisation.
4. **Escalation** alerts the responsible clinician, then nurse outreach, when nothing is booked.
5. **Patient messages** are drafted in plain language and the patient's preferred language, fact-checked,
   and approved by a clinician before sending. Urgent findings always go to a phone call instead.
6. **An equity view** shows which groups of patients are being missed.
7. **An audit log** records every AI output, rule decision and human action.

AI only reads and drafts. Rules do the tracking. Clinicians make every decision.

## Success measures

| Measure | Why it matters |
|---|---|
| Recall of follow-up extraction (especially urgent ones) | Missing a recommendation is the most dangerous error |
| Precision of extraction | Too many false alerts and clinicians stop trusting the tool |
| % of follow-ups completed on time | The outcome that actually protects patients |
| Time from due date to escalation | How fast a gap is caught |
| On-time completion by age, language and deprivation | Whether the tool closes gaps or widens them |

## Scope of this prototype

In scope: 104 synthetic full-format breast-pathway reports; AI (Claude) extraction with validation and an offline
fallback; tracking across two fictional trusts; escalation; translated, fact-checked, clinician-approved messages;
a patient portal with 18 languages, easy read, large text, high contrast, read aloud and replies; equity view;
evaluation; audit log; FHIR Task export.

Out of scope (needed for real use): real patient data, live integration with record systems (FHIR/HL7),
clinical safety case (DCB0129/DCB0160), DPIA, data-sharing agreements, professional translation, and validation
on real reports.
