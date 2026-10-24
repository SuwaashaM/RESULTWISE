# Synthetic data

> **Everything in this folder is synthetic. No real patient data was used at any stage, not even anonymised.**
> Every person, clinician and hospital is invented. NHS numbers come from the **999 test range** (never issued to
> real patients). Phone numbers come from Ofcom's ranges reserved for TV and drama (**01632 960xxx** landlines,
> **07700 900xxx** mobiles).

## What's here

| File | What it is | Used by |
|---|---|---|
| `reports.json` | **104 full NHS-style scan reports** with correct answers attached | Python prototype, evaluation |
| `heldout_reports.json` | **10 held-out reports**, written after the rules were built and never used to tune them | Evaluation (the fair test) |
| `patients.csv` | **60 patients** | Python prototype |
| `bookings.csv` | Bookings across the two fictional hospitals, some deliberately missing | Tracking rules |
| `history.csv` | **900 past follow-ups** with outcomes, with known inequalities built in | Equity view |
| `lovable_demo/demo_cases.json` | The **9 patients / 10 cases** used in the web app, plus pre-written translations | Web app (Lovable) |
| `sample_reports/` | **3 sample reports** as `.txt`, `.pdf` and `.docx`, to try the upload in the web app | Web app "Add a report" |
| `generate_data.py`, `cohort.py` | The scripts that generate the files above (fixed random seed, so the output is the same every time) | `python data/generate_data.py` |

## How the reports were built

- **28 hand-written story reports** around named patients (e.g. Halina's heart scan at one hospital, due at another).
- **76 generated reports** from **17 breast cancer scenarios**: heart scans during HER2 treatment, bone density
  scans on hormone tablets, surveillance mammograms, unclear (indeterminate) breast imaging, suspicious findings,
  and incidental findings on staging CT.
- Each scenario is written in **different styles** to test the AI: formal, abbreviated (`rpt TTE 6/52`), hedged
  (`may be helpful`), hidden in the findings instead of the conclusion, negated (`no further follow-up required`),
  two or three actions in one report, and already actioned.
- Each report has the full NHS layout: header (hospital, patient, NHS test number, date of birth), examination,
  accession number, referrer, clinical indication, comparison, technique, findings, conclusion, reporting doctor.

## Data dictionary

**`reports.json` / `heldout_reports.json`** (one object per report)

| Field | Meaning |
|---|---|
| `id` | Report ID (`R01`, `C001`, `H01`…) |
| `patient_id` | Links to `patients.csv` |
| `report_date` | Date reported |
| `source_trust` / `follow_up_trust` | Hospital that wrote the report / hospital where the follow-up should happen |
| `modality` | Type of scan |
| `difficulty` | Writing style being tested (formal, abbreviated, hedged, negation, buried in findings…) |
| `text` | Full report text |
| `gold` | Correct answers: list of `{follow_up_test, due_in_days, urgency}` (empty when no follow-up is needed) |

**`patients.csv`**: `id, name, age, sex, language, channel, imd_quintile, home_trust, phone, nhs_number`
- `language`: English, Polish, Urdu, Tamil, Bengali, Punjabi, Romanian, Somali
- `channel`: app, phone, letter, carer
- `imd_quintile`: deprivation, 1 = most deprived, 5 = least deprived

**`bookings.csv`**: `patient_id, test, trust, made_on, scheduled_for`

**`history.csv`**: `task_id, age, age_band, language, imd_quintile, channel, test, completed_on_time`

## Bias built in on purpose

To test whether Resultwise can **spot** inequality, `history.csv` has known gaps built in. The base chance of a
follow-up happening on time is 90%, and it drops by:

| Group | Drop |
|---|---|
| Age 65–79 / 80+ | 5 / 17 points |
| Preferred language not English | 12 points |
| Deprivation quintile 1 / 2 | 9 / 4 points |

The Equity view should surface exactly these groups. If it didn't, the tool would be hiding the problem.

## Limits

These reports were written by our team, so real reports will be messier and more varied. The held-out set is
small (10 reports). All reports are in English. Real validation would need de-identified real reports under
proper approvals.
