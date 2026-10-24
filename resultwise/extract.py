"""Report -> structured follow-up tasks.

Two engines share one contract (schema.Extraction):
  * offline : transparent rule-based extractor. No API key, no internet. Used as the demo fallback
              and as a baseline to compare the LLM against.
  * claude / openai : LLM with a strict JSON prompt, validated by Pydantic.

Whatever the engine, run_extraction() then applies safety checks:
  - output must validate against the schema (else -> human review, never dropped)
  - the "evidence" quote must really appear in the report (catches hallucinated follow-ups)
  - low confidence -> human review
  - urgent -> clinician phone call, never an automated patient message
"""
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from . import llm
from .schema import TEST_TYPES, Extraction, FollowUp

REVIEW_THRESHOLD = 0.7

# ----------------------------------------------------------------------------- offline engine

NEGATION = re.compile(
    r"\bno further\b|\bnot (required|necessary|needed|indicated)\b|\bno\b[^.;]{0,40}\b(required|necessary|needed)\b"
    r"|\bno (imaging )?follow[- ]?up\b", re.I)
TRIGGER = re.compile(
    r"\brecommend|\badvised?\b|\bsuggest|\bconsider\b|\brepeat\b|\brpt\b|\bplan\b|\bwould be helpful\b"
    r"|\bsurveillance\b|\bannual\b|\bnext\b|\bfollow[- ]?up\b|\brefer\b|\bcontinue\b", re.I)
HEDGE = re.compile(r"\bconsider\b|\bpossibly\b|\bif clinically indicated\b|\bmay\b|\bcould\b|\blikely of no\b", re.I)
URGENT = re.compile(r"(?<!non-)\burgent(ly)?\b", re.I)
SUSPICIOUS = re.compile(r"\b[RMU][45]\b|\bsuspicious\b|\bmalignan", re.I)
NEG_BEFORE = re.compile(r"\b(no|without|not)\b[^.]{0,25}$", re.I)

TEST_PATTERNS = [
    ("breast_biopsy", r"\bbiops|\bFNA\b"),
    ("echocardiogram", r"\becho(cardiogra\w*)?\b|\bTTE\b"),
    ("dexa", r"\bDXA\b|\bDEXA\b|bone density"),
    ("mri_liver", r"\bMRI (of the )?liver\b|\bliver MRI\b"),
    ("breast_mri", r"\bMRI (of the )?breasts?\b|\bbreast MRI\b"),
    ("thyroid_ultrasound", r"\bthyroid ultrasound\b|\bultrasound (of the )?thyroid\b"),
    ("breast_ultrasound", r"\bultrasound\b|\bUSS?\b"),
    ("ct_chest", r"\bCT\b"),
    ("mammogram", r"\bmammogra"),
    ("specialist_review", r"\breview\b|\bclinic\b|\brefer"),
]

WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "six": 6, "eight": 8, "twelve": 12, "eighteen": 18}
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _to_days(n: int, unit: str) -> int:
    unit = unit.lower().rstrip("s")
    if unit == "month" and n % 12 == 0:
        return 365 * n // 12
    return n * UNIT_DAYS[unit]


def parse_timeframe(text: str) -> int | None:
    m = re.search(r"\b(\d+|one|two|three|four|six|eight|twelve|eighteen)[\s-]*(day|week|month|year)s?\b", text, re.I)
    if m and not re.search(r"monthly", m.group(0), re.I):
        n = WORDNUM.get(m.group(1).lower()) or int(m.group(1))
        return _to_days(n, m.group(2))
    m = re.search(r"\b(\d+)-(monthly|weekly|yearly)\b", text, re.I)
    if m:
        return _to_days(int(m.group(1)), {"monthly": "month", "weekly": "week", "yearly": "year"}[m.group(2).lower()])
    m = re.search(r"\b(\d+)/(52|12|7)\b", text)
    if m:
        return _to_days(int(m.group(1)), {"52": "week", "12": "month", "7": "day"}[m.group(2)])
    if re.search(r"\bannual(ly)?\b|\byearly\b", text, re.I):
        return 365
    return None


def _positive_match(pattern: re.Pattern, text: str) -> bool:
    for m in pattern.finditer(text):
        if not NEG_BEFORE.search(text[:m.start()]):
            return True
    return False


def _sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def offline_extract(report_text: str) -> Extraction:
    suspicious = _positive_match(SUSPICIOUS, report_text)
    sents = _sentences(report_text)
    out: list[FollowUp] = []
    seen = set()
    for idx, sent in enumerate(sents):
        if idx == 0 or re.match(r"^(indication|history|clinical details)\b", sent, re.I):
            continue  # report title / clinical context, not a recommendation
        if NEGATION.search(sent):
            continue
        if not TRIGGER.search(sent):
            continue
        clauses = [c.strip() for c in re.split(r";|,(?= but)| and (?=\w)", sent) if c.strip()]
        n_test_clauses = sum(
            1 for c in clauses
            if any(re.search(p, re.sub(r"ultrasound-guided|US-guided", "", c, flags=re.I), re.I) for _, p in TEST_PATTERNS))
        for clause in clauses:
            if NEGATION.search(clause):
                continue
            cleaned = re.sub(r"ultrasound-guided|US-guided", "", clause, flags=re.I)
            for test, pat in TEST_PATTERNS:
                if not re.search(pat, cleaned, re.I):
                    continue
                if test in seen:
                    break
                days = parse_timeframe(clause)
                if days is None and n_test_clauses == 1:
                    days = parse_timeframe(sent)
                urgent = bool(URGENT.search(clause)) or (
                    suspicious and test in ("breast_biopsy", "breast_ultrasound", "specialist_review"))
                conf = 0.9
                if HEDGE.search(sent):
                    conf = 0.6
                if days is None:
                    if urgent or test == "breast_biopsy":
                        days = 14
                    elif test == "specialist_review":
                        days = 28
                    else:
                        days, conf = 90, min(conf, 0.55)
                urgency = "urgent" if urgent else ("soon" if days <= 42 else "routine")
                finding = sents[idx - 1] if (re.match(r"^(conclusion:\s*)?recommend", sent, re.I) and idx > 0) else sent
                out.append(FollowUp(finding=finding[:300], follow_up_test=test, due_in_days=days, urgency=urgency,
                                    evidence=clause[:600], confidence=conf))
                seen.add(test)
                break  # one test per clause
    reason = None if out else "No follow-up recommendation found (or explicitly not required)."
    return Extraction(follow_ups=out, no_follow_up_reason=reason)


# ----------------------------------------------------------------------------- LLM engine

SYSTEM_PROMPT = f"""You extract follow-up recommendations from radiology, echocardiography and DXA reports
for a patient-safety tracking tool. You do not diagnose. You only record what the report recommends.

Return ONLY a JSON object with this exact shape:
{{"follow_ups": [{{"finding": str, "follow_up_test": one of {TEST_TYPES},
  "due_in_days": int, "urgency": "routine"|"soon"|"urgent",
  "evidence": str (an exact verbatim quote from the report containing the recommendation),
  "confidence": float 0-1}}],
 "no_follow_up_reason": str or null}}

Rules:
- One item per distinct recommended test or referral. Clinic/specialist/MDT referrals -> "specialist_review".
- Any ultrasound of breast or axilla -> "breast_ultrasound". CT of chest/abdomen/pelvis -> "ct_chest".
- Do NOT create items for things stated as not required, already done, or historical.
- due_in_days: convert the stated timeframe (week=7, month=30, 12 months/1 year=365, 6/52=6 weeks,
  "3-monthly"=90, "annual"=365). If no timeframe: urgent or biopsy -> 14, clinic review -> 28, otherwise 90
  and confidence <= 0.55.
- urgency: "urgent" if the report says urgent or the finding is graded suspicious (R4/R5, U4/U5, M4/M5) and
  the action is biopsy, ultrasound or clinic referral; else "soon" if due_in_days <= 42; else "routine".
  "non-urgent" is NOT urgent.
- Hedged wording ("consider", "if clinically indicated", "possibly") -> confidence <= 0.6.
- evidence must be copied exactly from the report text.
- If nothing is recommended, return an empty follow_ups list and a short no_follow_up_reason."""


def llm_extract(report_text: str, provider: str, key: str | None = None) -> Extraction:
    raw = llm.complete(provider, SYSTEM_PROMPT, f"REPORT:\n{report_text}", key=key, json_mode=True)
    return Extraction.model_validate(llm.parse_json(raw))


# ----------------------------------------------------------------------------- safety layer

@dataclass
class ExtractionResult:
    extraction: Extraction | None
    engine_used: str
    issues: list[str] = field(default_factory=list)
    review_flags: list[bool] = field(default_factory=list)  # per follow-up: needs human review?


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def run_extraction(report_text: str, engine: str = "offline", key: str | None = None) -> ExtractionResult:
    issues: list[str] = []
    engine_used = engine
    extraction = None
    if engine in ("claude", "openai"):
        for attempt in (1, 2):
            try:
                extraction = llm_extract(report_text, engine, key)
                break
            except ValidationError as e:
                issues.append(f"AI output failed schema validation (attempt {attempt}): {e.errors()[0]['msg']}")
            except (llm.LLMError, ValueError) as e:
                issues.append(f"AI unavailable ({e}); used offline extractor and flagged for review.")
                break
        if extraction is None:
            extraction = offline_extract(report_text)
            engine_used = "offline (fallback)"
    else:
        extraction = offline_extract(report_text)

    flags = []
    norm_report = _norm(report_text)
    for f in extraction.follow_ups:
        needs_review = f.confidence < REVIEW_THRESHOLD or engine_used == "offline (fallback)"
        if _norm(f.evidence) not in norm_report:
            issues.append(f"Evidence for '{f.follow_up_test}' not found verbatim in report - possible hallucination.")
            needs_review = True
        flags.append(needs_review)
    return ExtractionResult(extraction, engine_used, issues, flags)
