"""Generate the Resultwise synthetic dataset.

Everything here is invented. No real patients, reports, hospitals or phone numbers.
Trust names are fictional; phone numbers use the Ofcom 01632 960xxx drama range.

Outputs (in this folder):
  patients.csv   - synthetic breast-pathway patients
  reports.json   - labelled radiology / echo / DXA reports (gold follow-ups for evaluation)
  bookings.csv   - scan bookings across two fictional trusts (some never made)
  history.csv    - 900 past follow-up tasks with outcomes, for the equity view.
                   A disparity is deliberately built in so the feature has something to show.

Run:  python data/generate_data.py
"""
import csv
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cohort  # noqa: E402

HERE = Path(__file__).parent
TRUST_A = "Northbridge Hospitals"
TRUST_B = "Valeford Hospitals"

# id, name, age, sex, language, channel, imd_quintile (1 = most deprived), home_trust
PATIENTS = [
    ("P001", "Halina Nowak", 61, "F", "Polish", "app", 3, TRUST_A),
    ("P002", "Susan Whitaker", 67, "F", "English", "app", 4, TRUST_B),
    ("P003", "Amina Hussain", 52, "F", "Urdu", "letter", 1, TRUST_A),
    ("P004", "Chloe Barnes", 41, "F", "English", "app", 3, TRUST_A),
    ("P005", "Patricia Coleman", 58, "F", "English", "app", 4, TRUST_A),
    ("P006", "Kavitha Raman", 49, "F", "Tamil", "app", 2, TRUST_A),
    ("P007", "Margaret Ellis", 72, "F", "English", "letter", 2, TRUST_A),
    ("P008", "Joan Pearson", 81, "F", "English", "carer", 1, TRUST_A),
    ("P009", "Nadia Begum", 63, "F", "Urdu", "phone", 1, TRUST_A),
    ("P010", "Rebecca Hall", 55, "F", "English", "app", 5, TRUST_A),
    ("P011", "Linda Moore", 69, "F", "English", "app", 3, TRUST_A),
    ("P012", "Ewa Kowalska", 47, "F", "Polish", "app", 2, TRUST_A),
    ("P013", "Doreen Walsh", 84, "F", "English", "carer", 2, TRUST_A),
    ("P014", "Sarah Ahmed", 59, "F", "English", "app", 3, TRUST_A),
    ("P015", "Emily Turner", 38, "F", "English", "app", 5, TRUST_A),
    ("P016", "Meena Sivakumar", 53, "F", "Tamil", "app", 4, TRUST_A),
    ("P017", "Hannah Price", 45, "F", "English", "app", 4, TRUST_A),
    ("P018", "Barbara Hughes", 74, "F", "English", "letter", 3, TRUST_A),
    ("P019", "Zofia Wiśniewska", 50, "F", "Polish", "app", 2, TRUST_A),
    ("P020", "Carl Bennett", 66, "M", "English", "app", 3, TRUST_A),
    ("P021", "Fatima Khan", 57, "F", "Urdu", "phone", 1, TRUST_A),
    ("P022", "Jennifer Lloyd", 62, "F", "English", "app", 4, TRUST_A),
    ("P023", "Priya Natarajan", 44, "F", "Tamil", "app", 3, TRUST_A),
    ("P024", "Elaine Foster", 78, "F", "English", "letter", 2, TRUST_A),
]

TRUST_PHONE = {TRUST_A: "01632 960 101", TRUST_B: "01632 960 202"}


def fu(test, days, urgency):
    return {"follow_up_test": test, "due_in_days": days, "urgency": urgency}


# Each report: id, patient, date, source trust, trust expected to do the follow-up,
# modality, text, gold follow-ups, difficulty tag, and whether it is already processed at demo start.
REPORTS = [
    dict(id="R01", patient_id="P001", report_date="2026-08-10", source_trust=TRUST_A, follow_up_trust=TRUST_B,
         modality="Echocardiogram", difficulty="cross-trust handover",
         text=("Transthoracic echocardiogram.\nIndication: on trastuzumab, 3-monthly cardiac surveillance.\n"
               "Findings: Left ventricle normal in size. LVEF 57% (baseline 62%). No regional wall motion abnormality. "
               "Valves structurally normal.\nConclusion: LVEF within normal limits with a small fall from baseline. "
               "Continue trastuzumab. Repeat echocardiogram in 12 weeks as per surveillance protocol; this will be "
               "performed at Valeford Hospitals cardio-oncology service."),
         gold=[fu("echocardiogram", 84, "routine")]),
    dict(id="R02", patient_id="P002", report_date="2025-11-20", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Mammogram", difficulty="negation + recommendation",
         text=("Bilateral mammography.\nHistory: left wide local excision 2023.\n"
               "Findings: Post-surgical changes in the left breast, stable. No suspicious mass, calcification or "
               "architectural distortion. Right breast normal.\nConclusion: No mammographic evidence of recurrence. "
               "Continue annual mammographic surveillance."),
         gold=[fu("mammogram", 365, "routine")]),
    dict(id="R03", patient_id="P003", report_date="2026-10-20", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Mammogram + ultrasound", difficulty="suspicious finding",
         text=("Screening assessment.\nRight breast: 9 mm irregular mass at 10 o'clock. Ultrasound shows a "
               "hypoechoic irregular lesion, U4.\nConclusion: R4/U4 - suspicious. Recommend urgent "
               "ultrasound-guided core biopsy."),
         gold=[fu("breast_biopsy", 14, "urgent")]),
    dict(id="R04", patient_id="P004", report_date="2026-10-16", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Breast ultrasound", difficulty="indeterminate",
         text=("Ultrasound left breast.\nFindings: 14 mm well-circumscribed oval hypoechoic lesion, parallel "
               "orientation, likely fibroadenoma. Graded U3 (indeterminate) given patient age.\n"
               "Conclusion: Recommend core biopsy for histological confirmation."),
         gold=[fu("breast_biopsy", 14, "soon")]),
    dict(id="R05", patient_id="P005", report_date="2026-09-02", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Breast ultrasound", difficulty="no follow-up",
         text=("Ultrasound right breast.\nFindings: 8 mm simple cyst at 2 o'clock. No solid component.\n"
               "Conclusion: U2 benign. No further imaging required; return to routine screening."),
         gold=[]),
    dict(id="R06", patient_id="P006", report_date="2026-10-22", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Echocardiogram", difficulty="two follow-ups, one urgent",
         text=("Echocardiogram.\nIndication: on trastuzumab and pertuzumab.\nFindings: LVEF 47% (previous 61%), an "
               "absolute fall of 14 percentage points. Mild global hypokinesis.\nConclusion: Significant fall in LVEF "
               "meeting criteria for cardiotoxicity. Recommend urgent cardio-oncology review and repeat echo in "
               "3 weeks. Oncology team informed by telephone."),
         gold=[fu("specialist_review", 14, "urgent"), fu("echocardiogram", 21, "soon")]),
    dict(id="R07", patient_id="P007", report_date="2026-09-15", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="DXA", difficulty="routine",
         text=("DXA scan.\nIndication: on letrozole since 2025.\nFindings: Lumbar spine T-score -1.8. Total hip "
               "T-score -1.4.\nConclusion: Osteopenia. Recommend repeat DXA in 2 years."),
         gold=[fu("dexa", 730, "routine")]),
    dict(id="R08", patient_id="P008", report_date="2026-09-20", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="DXA", difficulty="two follow-ups",
         text=("DXA scan.\nIndication: on anastrozole.\nFindings: L1-L4 T-score -2.7. Femoral neck T-score -2.1.\n"
               "Conclusion: Osteoporosis at the lumbar spine. Bone health clinic review advised within 6 weeks "
               "regarding bisphosphonate therapy. Repeat DXA in 12 months."),
         gold=[fu("specialist_review", 42, "soon"), fu("dexa", 365, "routine")]),
    dict(id="R09", patient_id="P009", report_date="2026-08-20", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="CT chest/abdomen/pelvis", difficulty="incidental finding",
         text=("CT chest, abdomen and pelvis (staging).\nFindings: No axillary or mediastinal lymphadenopathy. A 6 mm "
               "solid nodule in the right lower lobe, nonspecific. Liver, adrenals and bones unremarkable.\n"
               "Conclusion: No evidence of metastatic disease. Indeterminate 6 mm pulmonary nodule; suggest "
               "follow-up CT chest in 3 months to assess stability given oncological history."),
         gold=[fu("ct_chest", 90, "routine")]),
    dict(id="R10", patient_id="P010", report_date="2026-10-05", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="CT chest/abdomen/pelvis", difficulty="buried in findings",
         text=("CT chest, abdomen and pelvis.\nFindings: There is a 12 mm low-attenuation lesion in segment 7 of the "
               "liver which is too small to characterise; MRI liver within 4 weeks would be helpful. Lungs clear. "
               "No bone lesions.\nConclusion: No definite metastatic disease."),
         gold=[fu("mri_liver", 28, "soon")]),
    dict(id="R11", patient_id="P011", report_date="2026-09-12", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="CT chest", difficulty="no follow-up",
         text=("CT chest.\nFindings: Previously noted 5 mm nodule in the left upper lobe is unchanged compared with "
               "the 2024 CT, now stable over 2 years.\nConclusion: Benign behaviour. No further follow-up of the "
               "nodule is required."),
         gold=[]),
    dict(id="R12", patient_id="P012", report_date="2026-07-30", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Echocardiogram", difficulty="routine",
         text=("Echocardiogram.\nIndication: baseline prior to trastuzumab.\nFindings: LVEF 64%. Normal study.\n"
               "Conclusion: Proceed with treatment; next surveillance echo in 3 months."),
         gold=[fu("echocardiogram", 90, "routine")]),
    dict(id="R13", patient_id="P013", report_date="2025-10-10", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Mammogram", difficulty="routine",
         text=("Mammography.\nHistory: right mastectomy 2022.\nFindings: Left breast scattered fibroglandular "
               "density. A few benign-appearing calcifications, unchanged.\nConclusion: M2 benign. Annual "
               "mammography of the left breast as per surveillance programme."),
         gold=[fu("mammogram", 365, "routine")]),
    dict(id="R14", patient_id="P014", report_date="2026-10-23", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Mammogram", difficulty="suspicious, three actions",
         text=("Surveillance mammography.\nHistory: left wide local excision 2024.\nFindings: New area of "
               "architectural distortion at the scar site, not seen on the 2025 study.\nConclusion: M4 - "
               "suspicious. Recommend further assessment with ultrasound and core biopsy; refer to breast clinic "
               "urgently."),
         gold=[fu("breast_ultrasound", 14, "urgent"), fu("breast_biopsy", 14, "urgent"),
               fu("specialist_review", 14, "urgent")]),
    dict(id="R15", patient_id="P015", report_date="2026-10-01", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Axillary ultrasound", difficulty="hedged",
         text=("Ultrasound left axilla.\nFindings: A 9 mm lymph node with slightly thickened cortex (3.5 mm). "
               "Possibly reactive following recent vaccination.\nConclusion: Consider repeat ultrasound in 6 weeks "
               "if clinically indicated."),
         gold=[fu("breast_ultrasound", 42, "routine")]),
    dict(id="R16", patient_id="P016", report_date="2026-09-25", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Echocardiogram", difficulty="abbreviations",
         text=("TTE: LVEF 55%, GLS -17%. Rx: T-DM1.\nImp: borderline GLS reduction (-21% to -17%).\n"
               "Plan: rpt TTE 6/52."),
         gold=[fu("echocardiogram", 42, "soon")]),
    dict(id="R17", patient_id="P017", report_date="2026-09-28", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Mammogram", difficulty="no follow-up",
         text=("Diagnostic mammogram.\nIndication: left breast pain.\nFindings: No mass, no suspicious "
               "calcification.\nConclusion: M1 normal. No imaging follow-up required. Return to GP."),
         gold=[]),
    dict(id="R18", patient_id="P018", report_date="2026-06-01", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="DXA", difficulty="routine",
         text=("DXA baseline before starting anastrozole.\nFindings: T-scores spine -0.6, hip -0.4. Normal bone "
               "mineral density.\nConclusion: Repeat DXA in 2 years while on aromatase inhibitor."),
         gold=[fu("dexa", 730, "routine")]),
    dict(id="R19", patient_id="P019", report_date="2026-10-19", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Breast MRI", difficulty="indeterminate",
         text=("MRI breasts (extent of disease).\nKnown 18 mm right breast carcinoma. A 6 mm enhancing focus in the "
               "left breast at 2 o'clock, indeterminate (MRI 3).\nConclusion: Recommend second-look ultrasound of "
               "the left breast within 2 weeks."),
         gold=[fu("breast_ultrasound", 14, "soon")]),
    dict(id="R20", patient_id="P020", report_date="2026-09-01", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="CT chest/abdomen/pelvis", difficulty="hedged incidental",
         text=("CT chest, abdomen and pelvis (restaging, metastatic breast cancer).\nFindings: Interval decrease in "
               "size of liver metastases. Stable sclerotic bone lesions. New 4 mm nodule in the right middle lobe, "
               "likely of no significance, but attention on next restaging CT in 3 months is suggested.\n"
               "Conclusion: Partial response."),
         gold=[fu("ct_chest", 90, "routine")]),
    dict(id="R21", patient_id="P021", report_date="2026-08-05", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Echocardiogram", difficulty="routine",
         text=("Echocardiogram.\nIndication: on trastuzumab, cycle 9.\nFindings: LVEF 60%, stable.\n"
               "Conclusion: Continue 3-monthly echo surveillance until completion of trastuzumab."),
         gold=[fu("echocardiogram", 90, "routine")]),
    dict(id="R22", patient_id="P022", report_date="2026-09-08", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Liver MRI", difficulty="no follow-up",
         text=("MRI liver.\nFindings: 15 mm lesion in segment 4 shows features of a haemangioma.\n"
               "Conclusion: Benign haemangioma. No further imaging is necessary."),
         gold=[]),
    dict(id="R23", patient_id="P023", report_date="2026-10-24", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Breast ultrasound", difficulty="suspicious finding",
         text=("Ultrasound left breast for palpable lump.\nFindings: 22 mm irregular hypoechoic mass with posterior "
               "shadowing, U5. Left axillary node with effaced hilum.\nConclusion: Highly suspicious of malignancy. "
               "Recommend urgent core biopsy of the breast mass and axillary node."),
         gold=[fu("breast_biopsy", 14, "urgent")]),
    dict(id="R24", patient_id="P024", report_date="2026-09-10", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="DXA", difficulty="routine",
         text=("DXA scan.\nIndication: on exemestane.\nFindings: Spine T-score -2.2 (previously -1.9).\n"
               "Conclusion: Osteopenia with interval decline. Repeat DXA in 1 year."),
         gold=[fu("dexa", 365, "routine")]),
    dict(id="R25", patient_id="P012", report_date="2026-10-12", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Echocardiogram", difficulty="no follow-up",
         text=("Echocardiogram.\nFindings: LVEF 58%, stable. Trastuzumab course completed.\n"
               "Conclusion: No further echocardiographic surveillance required."),
         gold=[]),
    dict(id="R26", patient_id="P019", report_date="2026-10-21", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Mammogram", difficulty="no follow-up",
         text=("Mammogram after neoadjuvant chemotherapy.\nFindings: Marker clip in satisfactory position.\n"
               "Conclusion: No follow-up imaging needed before surgery."),
         gold=[]),
    dict(id="R27", patient_id="P005", report_date="2026-09-05", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="CT neck/chest", difficulty="incidental, non-urgent",
         text=("CT neck and chest.\nFindings: Incidental 15 mm left thyroid nodule. Lungs clear.\n"
               "Conclusion: Recommend non-urgent thyroid ultrasound within 3 months."),
         gold=[fu("thyroid_ultrasound", 90, "routine")]),
    dict(id="R28", patient_id="P020", report_date="2026-10-14", source_trust=TRUST_A, follow_up_trust=TRUST_A,
         modality="Axillary ultrasound", difficulty="already actioned",
         text=("Ultrasound left axilla.\nPerformed as the 6-week follow-up recommended on the previous study. "
               "The previously seen node now has a normal cortex.\nConclusion: Resolved reactive node. "
               "No further follow-up required."),
         gold=[]),
]

# Held-out reports: written AFTER the offline extractor was built and never used to tune it.
# Use these for an honest accuracy number. (The offline rules were tuned on REPORTS above.)
HELDOUT = [
    dict(id="H01", text=("Breast ultrasound.\nFindings: 5 mm complicated cyst, probably benign (U3).\nConclusion: "
                         "Short-interval follow-up ultrasound advised in six months."),
         gold=[fu("breast_ultrasound", 180, "routine")]),
    dict(id="H02", text=("Echocardiogram.\nFindings: LVEF 50%, down from 63% on trastuzumab.\nConclusion: Withhold "
                         "trastuzumab; cardiology opinion requested urgently. Re-scan in 4 weeks."),
         gold=[fu("specialist_review", 14, "urgent"), fu("echocardiogram", 28, "soon")]),
    dict(id="H03", text=("Screening mammogram.\nFindings: Benign appearances.\nConclusion: Routine recall in 3 years "
                         "via the screening programme."),
         gold=[fu("mammogram", 1095, "routine")]),
    dict(id="H04", text=("CT chest.\nFindings: 8 mm part-solid nodule in the left upper lobe.\nConclusion: Further CT "
                         "in 3 months; if persistent, discuss at lung MDT."),
         gold=[fu("ct_chest", 90, "routine")]),
    dict(id="H05", text=("DXA scan.\nFindings: Hip T-score -3.1.\nConclusion: Severe osteoporosis. Start "
                         "bisphosphonate via GP; repeat scan in 2 years."),
         gold=[fu("dexa", 730, "routine")]),
    dict(id="H06", text=("MRI breasts.\nFindings: No suspicious enhancement. Mild background parenchymal enhancement.\n"
                         "Conclusion: Annual MRI surveillance recommended (BRCA carrier)."),
         gold=[fu("breast_mri", 365, "routine")]),
    dict(id="H07", text=("Ultrasound liver.\nFindings: Two hyperechoic lesions, likely haemangiomas.\nConclusion: "
                         "No further imaging needed."),
         gold=[]),
    dict(id="H08", text=("Echocardiogram.\nFindings: LVEF 61%. Normal.\nConclusion: Continue routine 12-weekly "
                         "echoes during anti-HER2 therapy."),
         gold=[fu("echocardiogram", 84, "routine")]),
    dict(id="H09", text=("Mammogram right breast.\nFindings: 7 mm cluster of pleomorphic calcifications, R4.\n"
                         "Conclusion: Stereotactic biopsy recommended."),
         gold=[fu("breast_biopsy", 14, "urgent")]),
    dict(id="H10", text=("Staging bone scan.\nFindings: No abnormal uptake.\nConclusion: No follow-up imaging is "
                         "required on the basis of this study."),
         gold=[]),
]

# Reports that "arrive" during the demo (not processed at start)
UNPROCESSED_AT_START = {"R06", "R14", "R23"}

# Bookings: (patient, test, trust, made_on, scheduled_for)
# Missing bookings are deliberate: those are the gaps Resultwise should catch.
BOOKINGS = [
    ("P002", "mammogram", TRUST_B, "2026-10-01", "2026-11-16"),   # booked at a different trust after moving
    ("P003", "breast_biopsy", TRUST_A, "2026-10-21", "2026-10-24"),
    ("P004", "breast_biopsy", TRUST_A, "2026-10-17", "2026-10-23"),
    ("P006", "specialist_review", TRUST_A, "2026-10-23", "2026-10-28"),
    ("P010", "mri_liver", TRUST_A, "2026-10-10", "2026-10-29"),
    ("P012", "echocardiogram", TRUST_A, "2026-10-15", "2026-10-27"),
    ("P014", "breast_ultrasound", TRUST_A, "2026-10-24", "2026-10-30"),
    ("P014", "specialist_review", TRUST_A, "2026-10-24", "2026-10-30"),
    ("P015", "breast_ultrasound", TRUST_A, "2026-10-20", "2026-11-10"),
    ("P019", "breast_ultrasound", TRUST_A, "2026-10-21", "2026-10-26"),
    ("P020", "ct_chest", TRUST_A, "2026-11-10", "2026-11-25"),    # booked later in the demo timeline
    ("P023", "breast_biopsy", TRUST_A, "2026-10-24", "2026-10-27"),
]


def make_history(n=900, seed=7):
    """Past follow-up tasks with outcomes. Disparities are built in on purpose (synthetic demo)."""
    rng = random.Random(seed)
    langs = ["English"] * 78 + ["Polish"] * 6 + ["Urdu"] * 8 + ["Tamil"] * 4 + ["Bengali"] * 4
    tests = ["mammogram", "echocardiogram", "dexa", "ct_chest", "breast_ultrasound", "mri_liver"]
    rows = []
    for i in range(n):
        age = int(min(92, max(28, rng.gauss(62, 13))))
        band = "<50" if age < 50 else "50-64" if age < 65 else "65-79" if age < 80 else "80+"
        lang = rng.choice(langs)
        imd = rng.choice([1, 1, 2, 2, 3, 3, 4, 5])
        channel = rng.choice(["app", "app", "letter", "phone", "carer"]) if age >= 75 else rng.choice(
            ["app", "app", "app", "letter", "phone"])
        p = 0.90
        p -= {"<50": 0.0, "50-64": 0.0, "65-79": 0.05, "80+": 0.17}[band]
        p -= 0.0 if lang == "English" else 0.12
        p -= {1: 0.09, 2: 0.04, 3: 0.0, 4: 0.0, 5: 0.0}[imd]
        on_time = rng.random() < p
        rows.append(dict(task_id=f"H{i+1:04d}", age=age, age_band=band, language=lang, imd_quintile=imd,
                         channel=channel, test=rng.choice(tests), completed_on_time=int(on_time)))
    return rows


DEMO_START = date(2026, 10, 25)


def wrap_core(r: dict, patient: tuple, rng: random.Random, acc: int) -> str:
    """Turn a short core-story report into a full NHS-style report (header, indication, body, reporter)."""
    lines = [ln for ln in r["text"].split("\n") if ln.strip()]
    exam = lines[0].rstrip(".")
    indication, body = "Breast cancer pathway follow-up.", []
    for ln in lines[1:]:
        if re.match(r"^(indication|history):", ln, re.I):
            indication = ln.split(":", 1)[1].strip()
            indication = indication[:1].upper() + indication[1:]
        else:
            body.append(ln)
    kind = "echo" if re.search(r"echo|TTE", exam + " " + " ".join(body), re.I) else (
        "dxa" if re.search(r"DXA", exam) else "imaging")
    pid, name, age = patient[0], patient[1], patient[2]
    return cohort.format_report(r["source_trust"], name, cohort.nhs_number(int(pid[1:])), age,
                                date.fromisoformat(r["report_date"]), exam, kind, indication, "\n".join(body), rng, acc)


def main():
    rng = random.Random(2026)
    extra_patients = cohort.make_cohort_patients(len(PATIENTS) + 1, 36, rng)
    all_patients = PATIENTS + extra_patients
    with open(HERE / "patients.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "age", "sex", "language", "channel", "imd_quintile", "home_trust", "phone",
                    "nhs_number"])
        for p in all_patients:
            w.writerow(list(p) + [TRUST_PHONE[p[7]], cohort.nhs_number(int(p[0][1:]))])

    by_id = {p[0]: p for p in all_patients}
    core = []
    for k, r in enumerate(REPORTS):
        r = dict(r)
        r["processed_at_start"] = r["id"] not in UNPROCESSED_AT_START
        r["text"] = wrap_core(r, by_id[r["patient_id"]], rng, 50 + k)
        core.append(r)
    cohort_reports, cohort_bookings = cohort.make_cohort_reports(extra_patients, DEMO_START, rng)
    reports = core + cohort_reports
    with open(HERE / "reports.json", "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    BOOKINGS.extend(cohort_bookings)

    with open(HERE / "heldout_reports.json", "w", encoding="utf-8") as f:
        json.dump(HELDOUT, f, indent=2, ensure_ascii=False)

    with open(HERE / "bookings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["patient_id", "test", "trust", "made_on", "scheduled_for"])
        w.writerows(BOOKINGS)

    hist = make_history()
    with open(HERE / "history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist[0].keys()))
        w.writeheader()
        w.writerows(hist)

    n_fu = sum(len(r["gold"]) for r in reports)
    print(f"patients={len(all_patients)} reports={len(reports)} gold_follow_ups={n_fu} "
          f"bookings={len(BOOKINGS)} history={len(hist)}")


if __name__ == "__main__":
    main()
