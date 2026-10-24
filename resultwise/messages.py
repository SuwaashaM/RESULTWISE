"""Patient message drafting, translation and the back-translation / fact check.

Design rules (from our ethics plan):
  * The message never names the finding or a diagnosis, only the test that is due and how to book.
  * Urgent findings never get an automated message: a clinician phones the patient.
  * Every message is approved by a clinician before it is sent.
  * Translations are checked: key facts (date, phone number, name) must survive translation.
    With an LLM engine we also back-translate to English for the clinician to read.

Offline translations below are pre-written demo templates. Before any real use they must be
professionally translated and checked by native speakers.
"""
import re
from datetime import date

from . import llm
from .schema import PLAIN_TEST_NAME

EN_TEMPLATE = ("Hello {first_name}. Our records show you are due a {test} that has not been booked yet. "
               "It was due by {due}. Please call {phone} to book it as soon as possible. If you have already booked it, "
               "please let us know. This message was checked by your care team.")

TEMPLATES = {
    "Polish": ("Dzień dobry, {first_name}. Według naszych danych należy wykonać badanie: {test}. Nie zostało ono "
               "jeszcze umówione. Termin wykonania badania upłynął {due}. Prosimy jak najszybciej zadzwonić pod numer {phone}, aby je umówić. "
               "Jeśli badanie zostało już umówione, prosimy o informację. Ta wiadomość została sprawdzona przez "
               "Pani/Pana zespół medyczny."),
    "Urdu": ("ہیلو {first_name}۔ ہمارے ریکارڈ کے مطابق آپ کا {test} ہونا ہے جو ابھی تک بک نہیں ہوا۔ "
             "اس کی آخری تاریخ {due} تھی۔ براہ کرم جلد از جلد بک کرنے کے لیے {phone} پر کال کریں۔ "
             "اگر آپ پہلے ہی بک کر چکے ہیں تو براہ کرم ہمیں بتائیں۔ یہ پیغام آپ کی نگہداشت کی ٹیم نے چیک کیا ہے۔"),
    "Tamil": ("வணக்கம் {first_name}. எங்கள் பதிவுகளின்படி, நீங்கள் {test} செய்துகொள்ள வேண்டும், ஆனால் அது இன்னும் "
              "முன்பதிவு செய்யப்படவில்லை. இது {due} க்குள் செய்யப்பட்டிருக்க வேண்டும். விரைவில் முன்பதிவு செய்ய {phone} என்ற எண்ணை "
              "அழைக்கவும். நீங்கள் ஏற்கனவே முன்பதிவு செய்திருந்தால், தயவுசெய்து எங்களுக்குத் தெரிவிக்கவும். "
              "இந்தச் செய்தியை உங்கள் சிகிச்சைக் குழு சரிபார்த்துள்ளது."),
}

TEST_NAMES = {
    "Polish": {"mammogram": "mammografia", "breast_ultrasound": "USG piersi", "breast_mri": "rezonans magnetyczny piersi",
               "echocardiogram": "echokardiografia (USG serca)", "dexa": "densytometria (badanie gęstości kości)",
               "ct_chest": "tomografia komputerowa klatki piersiowej", "mri_liver": "rezonans magnetyczny wątroby",
               "thyroid_ultrasound": "USG tarczycy", "specialist_review": "wizyta kontrolna w poradni",
               "breast_biopsy": "biopsja piersi"},
    "Urdu": {"mammogram": "میموگرام", "breast_ultrasound": "چھاتی کا الٹراساؤنڈ", "breast_mri": "چھاتی کا ایم آر آئی",
             "echocardiogram": "دل کا الٹراساؤنڈ (ایکوکارڈیوگرام)", "dexa": "ہڈیوں کی کثافت کا اسکین (DEXA)",
             "ct_chest": "سینے کا سی ٹی اسکین", "mri_liver": "جگر کا ایم آر آئی", "thyroid_ultrasound": "تھائرائیڈ کا الٹراساؤنڈ",
             "specialist_review": "فالو اپ کلینک اپوائنٹمنٹ", "breast_biopsy": "چھاتی کی بایوپسی"},
    "Tamil": {"mammogram": "மேமோகிராம்", "breast_ultrasound": "மார்பக அல்ட்ராசவுண்ட் ஸ்கேன்",
              "breast_mri": "மார்பக MRI ஸ்கேன்", "echocardiogram": "இதய ஸ்கேன் (எக்கோகார்டியோகிராம்)",
              "dexa": "எலும்பு அடர்த்தி ஸ்கேன் (DEXA)", "ct_chest": "நெஞ்சு CT ஸ்கேன்",
              "mri_liver": "கல்லீரல் MRI ஸ்கேன்", "thyroid_ultrasound": "தைராய்டு அல்ட்ராசவுண்ட் ஸ்கேன்",
              "specialist_review": "மருத்துவ ஆய்வு சந்திப்பு", "breast_biopsy": "மார்பக பயாப்ஸி"},
}


def fmt_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%d/%m/%Y")


def draft_english(patient: dict, task: dict, phone: str) -> tuple[str, dict]:
    facts = {"first_name": patient["name"].split()[0], "due": fmt_date(task["due_date"]), "phone": phone,
             "test": PLAIN_TEST_NAME[task["test"]]}
    return EN_TEMPLATE.format(**facts), facts


def fact_check(text_en: str, text_tr: str, facts: dict) -> tuple[bool, list[str]]:
    """Every number in the English message (date, phone) and the patient's name must appear in the translation."""
    notes = []
    if facts["due"] not in text_tr:
        notes.append(f"Due date {facts['due']} does not appear exactly in the translation.")
    if facts["phone"] not in text_tr:
        notes.append(f"Phone number {facts['phone']} does not appear exactly in the translation.")
    en_numbers = re.findall(r"\d+", text_en)
    tr_numbers = re.findall(r"\d+", text_tr)
    for n in en_numbers:
        if tr_numbers.count(n) < en_numbers.count(n):
            notes.append(f"Number '{n}' from the English message is missing or changed in the translation.")
    if facts["first_name"] not in text_tr:
        notes.append("Patient name missing from translation.")
    notes = list(dict.fromkeys(notes))
    return (not notes), notes


TRANSLATE_RULES = ("Keep every date, phone number and the person's name exactly as written, using Western digits "
                   "0-9 and the name in Latin letters. Do not add, remove or soften any medical detail. "
                   "Reply with the translated text only, no notes.")

# Languages offered in the patient portal (BCP-47 codes are used for read-aloud voices)
LANGUAGES = {
    "English": "en-GB", "Polish": "pl-PL", "Urdu": "ur-PK", "Tamil": "ta-IN", "Bengali": "bn-BD",
    "Punjabi": "pa-IN", "Arabic": "ar-SA", "Romanian": "ro-RO", "Gujarati": "gu-IN", "Somali": "so-SO",
    "Portuguese": "pt-PT", "Spanish": "es-ES", "French": "fr-FR", "Lithuanian": "lt-LT", "Turkish": "tr-TR",
    "Chinese (Simplified)": "zh-CN", "Hindi": "hi-IN", "Welsh": "cy-GB",
}
RTL = {"Urdu", "Arabic"}


def llm_translate(text_en: str, language: str, engine: str, key=None) -> tuple[str, str]:
    """AI translation plus an independent back-translation into English for the clinician to read."""
    tr = llm.complete(engine, f"Translate this NHS patient message into {language}. Plain, kind, easy to read. "
                      + TRANSLATE_RULES, text_en, key=key, max_tokens=2000, fast=True).strip()
    back = llm.complete(engine, "Translate this message into English literally. Reply with the translation only.",
                        tr, key=key, max_tokens=2000, fast=True).strip()
    return tr, back


def translate(text_en: str, facts: dict, test: str, language: str, engine: str, key=None,
              inject_error: bool = False) -> tuple[str, str]:
    """Return (translation, back_translation). AI engines translate any language; offline uses templates."""
    if language == "English":
        return text_en, ""
    if engine in ("claude", "openai"):
        try:
            tr, back = llm_translate(text_en, language, engine, key)
            return (_inject(tr, facts) if inject_error else tr), back
        except llm.LLMError:
            pass  # fall through to the offline template if there is one
    tmpl = TEMPLATES.get(language)
    if not tmpl:
        return text_en, f"(no offline template for {language}: add an API key for AI translation)"
    tr = tmpl.format(first_name=facts["first_name"], test=TEST_NAMES[language][test], due=facts["due"], phone=facts["phone"])
    if inject_error:
        tr = _inject(tr, facts)
    return tr, "(offline mode: fact check only, no back-translation)"


EASY_READ_EN = ("{first_name}, you need a {test}.\n"
                "It was due on {due}.\n"
                "It is not booked yet.\n"
                "Please phone {phone} to book it.\n"
                "If you have booked it already, please tell us.")


def easy_read(facts: dict, language: str, engine: str, key=None) -> str:
    """Short sentences, one idea per line. Offline: English template. AI: any language."""
    base = EASY_READ_EN.format(**facts)
    if engine in ("claude", "openai"):
        try:
            return llm.complete(engine, (
                f"Rewrite this NHS patient message as an easy-read version in {language}: very short sentences, "
                "one idea per line, everyday words, about a reading age of 9. Keep the meaning exactly. "
                + TRANSLATE_RULES), base, key=key, max_tokens=1500, fast=True).strip()
        except llm.LLMError:
            pass
    return base


def _inject(tr: str, facts: dict) -> str:
    """Simulate a translation error by changing the due date (to demo the safety check)."""
    d, m, y = facts["due"].split("/")
    wrong = f"{m}/{d}/{y}" if d != m else f"{int(d) % 28 + 1:02d}/{m}/{y}"
    return tr.replace(facts["due"], wrong)
