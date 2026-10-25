"""Export a ResultWise task as a FHIR R4 Task resource (JSON).

Shows how a follow-up could travel between organisations and record systems using the standard
health-data format, instead of living inside one hospital's record. Synthetic data only.
"""
from .schema import PLAIN_TEST_NAME

STATUS = {"open": "requested", "due_soon": "requested", "overdue": "requested", "booked": "accepted",
          "completed": "completed", "dismissed": "cancelled"}
PRIORITY = {"routine": "routine", "soon": "asap", "urgent": "urgent"}


def task_resource(task: dict, patient: dict, report: dict) -> dict:
    return {
        "resourceType": "Task",
        "id": f"resultwise-{task['id']}",
        "meta": {"tag": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST",
                          "display": "test health data (synthetic)"}]},
        "status": STATUS.get(task["status"], "requested"),
        "businessStatus": {"text": task["status"].replace("_", " ")},
        "intent": "order",
        "priority": PRIORITY.get(task["urgency"], "routine"),
        "code": {"text": f"Follow-up: {PLAIN_TEST_NAME[task['test']]}"},
        "description": task["finding"],
        "focus": {"reference": f"DiagnosticReport/{report['id']}", "display": report["modality"]},
        "for": {"identifier": {"system": "https://fhir.nhs.uk/Id/nhs-number",
                               "value": (patient.get("nhs_number") or "").replace(" ", "")},
                "display": patient["name"]},
        "authoredOn": task["created_on"],
        "restriction": {"period": {"end": task["due_date"]}},
        "requester": {"display": report["source_trust"]},
        "owner": {"display": task["responsible_trust"]},
        "note": [{"text": f"Evidence from report: {task['evidence']}"},
                 {"text": f"AI confidence {task['confidence']:.2f}; review state {task['review_state']}"}],
    }
