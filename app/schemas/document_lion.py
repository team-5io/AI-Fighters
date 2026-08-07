from typing import Literal
from uuid import UUID

from app.schemas.base import CamelModel

TriggerType = Literal["manual", "auto"]
Severity = Literal["critical", "medium", "minor"]
IssueType = Literal["conflict", "inconsistency", "charter_violation"]
Verdict = Literal["approve", "reject_recommended"]


class ReviewRequest(CamelModel):
    document_id: UUID
    doc_pr_id: UUID | None = None
    trigger_type: TriggerType
    requested_by: UUID  # auto 호출(BE) 시에도 필수 — Doc PR 제출자의 userId


class ReviewIssue(CamelModel):
    severity: Severity
    issue_type: IssueType
    description: str
    related_document_id: UUID | None = None
    charter_rule_id: UUID | None = None
    location_ref: str | None = None


class ReviewResponse(CamelModel):
    review_id: UUID
    overall_verdict: Verdict
    issues: list[ReviewIssue]
