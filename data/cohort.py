"""Synthetic cohort: full NHS-style report formatting plus a scenario library with varied phrasing.

Everything here is invented: fictional trusts, patients and clinicians. NHS numbers use the 999 range
reserved for test data. Phrasing deliberately varies (formal, abbreviated, hedged, buried in findings,
explicit negation) so the extractor is tested on realistic variety, and every report carries gold labels.
"""
import random
from datetime import date, timedelta


def fu(test, days, urgency):
    return {"follow_up_test": test, "due_in_days": days, "urgency": urgency}


TRUST_A, TRUST_B = "Northbridge Hospitals", "Valeford Hospitals"
REPORTERS = {
    "imaging": ["Dr K. Mensah, Consultant Breast Radiologist", "Dr L. Harrington, Consultant Radiologist",
                "Dr S. Iqbal, Consultant Radiologist", "Dr M. Fenwick, Consultant Breast Radiologist"],
    "echo": ["J. Whitfield, Clinical Scientist (Echocardiography)", "R. Adeyemi, Clinical Scientist (Echocardiography)"],
    "dxa": ["Dr P. Lowe, Consultant in Bone Health", "A. Kaur, Clinical Scientist (Bone Densitometry)"],
}
REFERRERS = ["Dr A. Patel, Breast Oncology", "Ms H. Carver, Breast Surgery", "Dr T. Moreau, Clinical Oncology",
             "Dr N. Achebe, Breast Oncology", "Breast Care Nurse Specialist team"]

FIRST = ["Margaret", "Aisha", "Grace", "Agnieszka", "Shabana", "Lakshmi", "Rosa", "Eileen", "Ifeoma", "Claire",
         "Nasreen", "Teresa", "Rukhsana", "Joanne", "Marta", "Selvi", "Gillian", "Hafsa", "Dorothy", "Kiran",
         "Ioana", "Patience", "Lorraine", "Yasmin", "Beata", "Wendy", "Amarjit", "Helen", "Farida", "Sandra",
         "Comfort", "Pauline", "Asha", "Monika", "Brenda", "David"]
LAST = ["Ahmed", "Kowalczyk", "Brennan", "Okafor", "Rahman", "Murugan", "Silva", "Gallagher", "Thompson", "Bibi",
        "Nowicka", "Shah", "Chowdhury", "Walker", "Popescu", "Krishnan", "Hussain", "Clarke", "Kaur", "Ali",
        "Mensah", "Dobson", "Begum", "Lewandowska", "Ellis", "Sandhu", "Patel", "Osei", "Morgan", "Wright",
        "Abdi", "Taylor", "Iyer", "Nowak", "Reid", "Owen"]
LANG_FOR_SURNAME = {"Kowalczyk": "Polish", "Nowicka": "Polish", "Lewandowska": "Polish", "Nowak": "Polish",
                    "Murugan": "Tamil", "Krishnan": "Tamil", "Iyer": "Tamil", "Rahman": "Bengali",
                    "Chowdhury": "Bengali", "Begum": "Bengali", "Bibi": "Urdu", "Hussain": "Urdu", "Ali": "Urdu",
                    "Sandhu": "Punjabi", "Kaur": "Punjabi", "Popescu": "Romanian", "Abdi": "Somali"}


def nhs_number(i: int) -> str:
    n = f"999{i:07d}"
    return f"{n[:3]} {n[3:6]} {n[6:]}"


def make_cohort_patients(start_index: int, n: int, rng: random.Random):
    out = []
    for k in range(n):
        i = start_index + k
        first, last = FIRST[k % len(FIRST)], LAST[(k * 7) % len(LAST)]
        lang = LANG_FOR_SURNAME.get(last, "English")
        if lang != "English" and rng.random() < 0.4:
            lang = "English"  # many people with these surnames prefer English
        age = int(min(91, max(31, rng.gauss(61, 12))))
        channel = (rng.choice(["letter", "carer", "phone", "app"]) if age >= 78
                   else rng.choice(["app", "app", "app", "letter", "phone"]))
        sex = "M" if first == "David" else "F"
        imd = rng.choice([1, 1, 2, 2, 3, 3, 4, 5])
        out.append((f"P{i:03d}", f"{first} {last}", age, sex, lang, channel, imd,
                    TRUST_B if rng.random() < 0.25 else TRUST_A))
    return out


# ----------------------------------------------------------------------------- report formatting

def fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def format_report(trust, patient, nhs, age, report_date: date, exam, kind, indication, body,
                  rng: random.Random, accession_no: int, comparison=None, technique=None) -> str:
    dob = date(report_date.year - age, rng.randint(1, 12), rng.randint(1, 28))
    surname = patient.split()[-1].upper()
    given = " ".join(patient.split()[:-1])
    prefix = "NB" if trust == TRUST_A else "VF"
    lines = [
        f"{trust} - {'Echocardiography' if kind == 'echo' else 'Bone Densitometry' if kind == 'dxa' else 'Radiology'}",
        f"Patient name: {surname}, {given}    NHS number: {nhs}    DOB: {fmt(dob)}",
        f"Examination: {exam}",
        f"Date of examination: {fmt(report_date)}    Accession: {prefix}{report_date.year}{accession_no:06d}",
        f"Referred by: {rng.choice(REFERRERS)}",
        f"Clinical indication: {indication}",
    ]
    if comparison:
        lines.append(f"Comparison: {comparison}")
    if technique:
        lines.append(f"Technique: {technique}")
    lines.append("")
    lines.append(body.strip())
    lines.append("")
    lines.append(f"Reported by: {rng.choice(REPORTERS[kind])}    Verified: {fmt(report_date)}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- scenario library
# Each returns: exam, kind, indication, comparison, technique, body, gold, difficulty

def echo_routine(r):
    lv = r.randint(56, 66)
    plan = r.choice([
        ("Conclusion: Normal LV systolic function. Repeat echocardiogram in 3 months as per cardio-oncology "
         "surveillance protocol.", 90, "routine", "formal"),
        ("Impression: LVEF preserved. Next surveillance echo in 12 weeks.", 84, "routine", "formal"),
        ("Imp: LVEF preserved, no change. Plan: rpt TTE 3/12.", 90, "routine", "abbreviated"),
        ("Conclusion: Stable LV function. Continue 3-monthly echocardiographic surveillance while on trastuzumab.",
         90, "routine", "formal"),
    ])
    body = (f"Findings: Left ventricle normal in size with LVEF {lv}% (Simpson's biplane). Global longitudinal strain "
            f"-{r.randint(18, 22)}%. No regional wall motion abnormality. Valves structurally normal. No pericardial "
            f"effusion.\n{plan[0]}")
    return ("Transthoracic echocardiogram", "echo", f"On trastuzumab, cycle {r.randint(3, 15)}. Routine cardiac surveillance.",
            "Previous echocardiogram 3 months ago", None, body, [fu("echocardiogram", plan[1], plan[2])], plan[3])


def echo_drop(r):
    prev, now = r.randint(60, 65), r.randint(45, 51)
    variant = r.choice(["urgent", "soon"])
    if variant == "urgent":
        concl = (f"Conclusion: LVEF has fallen from {prev}% to {now}%, meeting criteria for cancer therapy-related "
                 "cardiac dysfunction. Urgent cardio-oncology review recommended. Repeat echocardiogram in 3 weeks.")
        gold = [fu("specialist_review", 14, "urgent"), fu("echocardiogram", 21, "soon")]
    else:
        concl = (f"Conclusion: Borderline reduction in LVEF ({prev}% to {now}%). Recommend cardio-oncology review within "
                 "4 weeks and repeat echocardiogram in 6 weeks.")
        gold = [fu("specialist_review", 28, "soon"), fu("echocardiogram", 42, "soon")]
    body = (f"Findings: LVEF {now}% (previously {prev}%). Mild global hypokinesis. GLS -{r.randint(13, 16)}%. "
            f"Right ventricle normal.\n{concl}")
    return ("Transthoracic echocardiogram", "echo", "On trastuzumab and pertuzumab. Surveillance echocardiogram.",
            "Echocardiogram 3 months ago", None, body, gold, "two actions")


def echo_complete(r):
    body = (f"Findings: LVEF {r.randint(57, 64)}%, unchanged. Normal diastolic function.\n"
            "Conclusion: Normal study. Trastuzumab course completed. No further echocardiographic surveillance is "
            "required.")
    return ("Transthoracic echocardiogram", "echo", "End of HER2-targeted therapy.", None, None, body, [], "negation")


def dxa_osteopenia(r):
    t = round(r.uniform(-2.4, -1.1), 1)
    plan = r.choice([("Recommend repeat DXA in 2 years.", 730), ("Repeat bone density scan in 24 months.", 730),
                     ("Follow-up DXA advised in 2 years while on aromatase inhibitor.", 730)])
    body = (f"Findings: Lumbar spine (L1-L4) T-score {t}. Total hip T-score {round(t + 0.4, 1)}. "
            f"Femoral neck T-score {round(t + 0.2, 1)}.\nConclusion: Osteopenia. {plan[0]}")
    return ("DXA bone densitometry", "dxa", f"On {r.choice(['letrozole', 'anastrozole', 'exemestane'])}. "
            "Baseline / monitoring bone health.", None, "Lumbar spine and left hip", body,
            [fu("dexa", plan[1], "routine")], "routine")


def dxa_osteoporosis(r):
    t = round(r.uniform(-3.4, -2.5), 1)
    body = (f"Findings: Lumbar spine T-score {t}. Total hip T-score {round(t + 0.5, 1)}.\n"
            "Conclusion: Osteoporosis. Referral to the bone health clinic is advised within 6 weeks to consider "
            "bisphosphonate therapy. Repeat DXA in 12 months.")
    return ("DXA bone densitometry", "dxa", "On anastrozole. Monitoring bone health.", "DXA 2 years ago",
            "Lumbar spine and left hip", body,
            [fu("specialist_review", 42, "soon"), fu("dexa", 365, "routine")], "two actions")


def dxa_normal_none(r):
    body = (f"Findings: Spine T-score {round(r.uniform(-0.8, 0.6), 1)}, hip T-score {round(r.uniform(-0.6, 0.8), 1)}.\n"
            "Conclusion: Normal bone mineral density. On tamoxifen; no routine repeat scan is required.")
    return ("DXA bone densitometry", "dxa", "On tamoxifen. Baseline bone health.", None, None, body, [], "negation")


def mammo_surveillance(r):
    side = r.choice(["left", "right"])
    plan = r.choice([("Annual surveillance mammography recommended.", 365, "formal"),
                     ("Return for bilateral mammography in 12 months.", 365, "formal"),
                     ("Continue yearly mammographic surveillance.", 365, "formal")])
    body = (f"Findings: Post-surgical changes in the {side} breast, stable. No suspicious mass, calcification or "
            f"architectural distortion. Contralateral breast normal. Breast density B.\nConclusion: M2 benign. "
            f"No mammographic evidence of recurrence. {plan[0]}")
    return ("Bilateral mammography (surveillance)", "imaging", f"{side.capitalize()} wide local excision "
            f"{r.choice([2022, 2023, 2024])}. Annual surveillance.", "Mammography 12 months ago", None, body,
            [fu("mammogram", plan[1], "routine")], plan[2])


def mammo_final(r):
    body = ("Findings: Stable post-treatment appearances. No suspicious features.\nConclusion: M1. Five years of "
            "hospital surveillance now complete. No further hospital follow-up imaging required; the patient returns "
            "to the routine screening programme.")
    return ("Bilateral mammography (surveillance)", "imaging", "Year 5 surveillance after breast cancer.",
            "Mammography 12 months ago", None, body, [], "negation")


def mammo_suspicious(r):
    body = ("Findings: New 8 mm area of architectural distortion at the scar site, not present on the previous "
            "study.\nConclusion: M4 - suspicious for recurrence. Recommend ultrasound and core biopsy; refer to "
            "the breast clinic urgently.")
    return ("Bilateral mammography (surveillance)", "imaging", "Surveillance after breast cancer.",
            "Mammography 12 months ago", None, body,
            [fu("breast_ultrasound", 14, "urgent"), fu("breast_biopsy", 14, "urgent"),
             fu("specialist_review", 14, "urgent")], "suspicious")


def us_indeterminate(r):
    size = r.randint(9, 18)
    body = (f"Findings: {size} mm oval circumscribed hypoechoic lesion at {r.randint(1, 12)} o'clock, "
            f"{r.randint(2, 6)} cm from the nipple. Graded U3 (indeterminate).\n"
            "Conclusion: Recommend ultrasound-guided core biopsy for histological confirmation.")
    return ("Ultrasound breast", "imaging", "Palpable lump.", None, None, body,
            [fu("breast_biopsy", 14, "soon")], "indeterminate")


def us_probably_benign(r):
    body = (f"Findings: {r.randint(4, 7)} mm complicated cyst. No solid component. Probably benign.\n"
            "Conclusion: Short-interval follow-up ultrasound advised in 6 months.")
    return ("Ultrasound breast", "imaging", "Follow-up of previously seen cyst.", "Ultrasound 6 months ago", None,
            body, [fu("breast_ultrasound", 180, "routine")], "hedged")


def us_suspicious(r):
    body = (f"Findings: {r.randint(15, 30)} mm irregular hypoechoic mass with posterior shadowing, U5. Axillary node "
            "with thickened cortex.\nConclusion: Highly suspicious of malignancy. Recommend urgent core biopsy of "
            "the breast mass and axillary node.")
    return ("Ultrasound breast and axilla", "imaging", "Two-week-wait referral, palpable lump.", None, None, body,
            [fu("breast_biopsy", 14, "urgent")], "suspicious")


def us_benign(r):
    body = ("Findings: Simple cyst, no solid component.\nConclusion: U2 benign. No further imaging required; "
            "discharge to GP.")
    return ("Ultrasound breast", "imaging", "Breast pain.", None, None, body, [], "negation")


def ct_nodule(r):
    size = r.randint(5, 8)
    months = r.choice([3, 12])
    plan = r.choice([
        f"Conclusion: No evidence of metastatic disease. Indeterminate {size} mm pulmonary nodule; suggest follow-up "
        f"CT chest in {months} months.",
        f"Conclusion: No metastatic disease. A {size} mm nodule is likely benign but a further CT in {months} months "
        "would be prudent given the oncological history.",
    ])
    body = (f"Findings: No axillary, mediastinal or hilar lymphadenopathy. A {size} mm solid nodule in the "
            f"{r.choice(['right lower', 'left upper', 'right middle'])} lobe. Liver, adrenals and bones unremarkable.\n"
            + plan)
    days = 365 if months == 12 else 90
    return ("CT chest, abdomen and pelvis (staging)", "imaging", "Staging, newly diagnosed breast cancer.", None,
            "Portal venous phase", body, [fu("ct_chest", days, "routine")], "incidental")


def ct_liver_buried(r):
    body = (f"Findings: There is a {r.randint(9, 15)} mm low-attenuation lesion in segment {r.randint(5, 8)} of the "
            "liver which is too small to characterise; MRI liver within 4 weeks would be helpful. Lungs clear. "
            "No bone lesions.\nConclusion: No definite metastatic disease.")
    return ("CT chest, abdomen and pelvis (staging)", "imaging", "Staging.", None, "Portal venous phase", body,
            [fu("mri_liver", 28, "soon")], "buried in findings")


def ct_clear(r):
    body = ("Findings: No lymphadenopathy. Lungs clear. Liver, adrenals and skeleton unremarkable.\n"
            "Conclusion: No evidence of metastatic disease. No follow-up imaging is required on the basis of this "
            "study.")
    return ("CT chest, abdomen and pelvis (staging)", "imaging", "Staging.", None, "Portal venous phase", body,
            [], "negation")


def ct_thyroid(r):
    body = (f"Findings: Incidental {r.randint(12, 20)} mm left thyroid nodule. Lungs clear. No lymphadenopathy.\n"
            "Conclusion: No metastatic disease. Recommend non-urgent thyroid ultrasound within 3 months.")
    return ("CT neck and chest", "imaging", "Staging.", None, None, body,
            [fu("thyroid_ultrasound", 90, "routine")], "incidental")


SCENARIOS = [
    (echo_routine, 14), (echo_drop, 4), (echo_complete, 3), (dxa_osteopenia, 7), (dxa_osteoporosis, 3),
    (dxa_normal_none, 2), (mammo_surveillance, 14), (mammo_final, 3), (mammo_suspicious, 2),
    (us_indeterminate, 4), (us_probably_benign, 3), (us_suspicious, 2), (us_benign, 3),
    (ct_nodule, 5), (ct_liver_buried, 2), (ct_clear, 3), (ct_thyroid, 2),
]


def make_cohort_reports(patients, demo_start: date, rng: random.Random, n_reports: int = 76):
    """Spread scenarios across patients; choose report dates so due dates cluster around the demo window."""
    pool = [fn for fn, w in SCENARIOS for _ in range(w)]
    reports, bookings = [], []
    acc = 100
    for k in range(n_reports):
        p = patients[k % len(patients)]
        pid, name, age, _sex, lang, _ch, imd, trust = p
        exam, kind, indication, comparison, technique, body, gold, difficulty = rng.choice(pool)(rng)
        days = max([g["due_in_days"] for g in gold], default=60)
        offset = rng.randint(-35, 110)  # due date relative to demo start
        rdate = demo_start + timedelta(days=offset) - timedelta(days=min(days, 700))
        rdate = min(rdate, demo_start - timedelta(days=1))
        acc += rng.randint(1, 40)
        text = format_report(trust, name, nhs_number(int(pid[1:])), age, rdate, exam, kind, indication, body, rng, acc,
                             comparison, technique)
        rid = f"C{k + 1:03d}"
        reports.append(dict(id=rid, patient_id=pid, report_date=rdate.isoformat(), source_trust=trust,
                            follow_up_trust=trust, modality=exam, difficulty=difficulty, text=text, gold=gold,
                            processed_at_start=True))
        # Bookings: most follow-ups get booked; older, non-English and deprived patients less often (synthetic)
        for g in gold:
            p_book = 0.93 if g["urgency"] == "urgent" else 0.86
            p_book -= 0.15 if age >= 80 else 0.04 if age >= 65 else 0
            p_book -= 0.10 if lang != "English" else 0
            p_book -= 0.08 if imd == 1 else 0.03 if imd == 2 else 0
            if rng.random() < p_book:
                due = rdate + timedelta(days=g["due_in_days"])
                made = rdate + timedelta(days=rng.randint(2, max(3, int(g["due_in_days"] * 0.6))))
                sched = due - timedelta(days=rng.randint(0, max(1, min(14, g["due_in_days"] // 4))))
                if sched <= made:
                    sched = made + timedelta(days=3)
                where = trust if rng.random() > 0.08 else (TRUST_B if trust == TRUST_A else TRUST_A)
                bookings.append((pid, g["follow_up_test"], where, made.isoformat(), sched.isoformat()))
    return reports, bookings
