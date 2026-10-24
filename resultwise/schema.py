"""Data contracts. Every AI output must pass these Pydantic models before it can enter the database."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

TestType = Literal[
    "mammogram", "breast_ultrasound", "breast_biopsy", "breast_mri", "echocardiogram", "dexa",
    "ct_chest", "mri_liver", "thyroid_ultrasound", "specialist_review",
]
Urgency = Literal["routine", "soon", "urgent"]

TEST_TYPES = list(TestType.__args__)

# Plain-English names used in patient messages (no diagnosis is ever put in a message)
PLAIN_TEST_NAME = {
    "mammogram": "mammogram (breast X-ray)",
    "breast_ultrasound": "breast ultrasound scan",
    "breast_biopsy": "breast biopsy",
    "breast_mri": "breast MRI scan",
    "echocardiogram": "heart scan (echocardiogram)",
    "dexa": "bone density scan (DEXA)",
    "ct_chest": "chest CT scan",
    "mri_liver": "liver MRI scan",
    "thyroid_ultrasound": "thyroid ultrasound scan",
    "specialist_review": "follow-up clinic appointment",
}


class FollowUp(BaseModel):
    finding: str = Field(min_length=2, max_length=300)
    follow_up_test: TestType
    due_in_days: int = Field(gt=0, le=1095)
    urgency: Urgency
    evidence: str = Field(min_length=3, max_length=600, description="Verbatim quote from the report")
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    follow_ups: List[FollowUp]
    no_follow_up_reason: Optional[str] = None
