from typing import Literal
from uuid import UUID

from app.schemas.base import CamelModel

TriggerType = Literal["manual", "auto"]
Severity = Literal["critical", "medium", "minor"]
IssueType = Literal["conflict", "inconsistency", "charter_violation"]
Verdict = Literal["approve", "reject_recommended"]


class ReviewRequest(CamelModel):
    document_id: int
    doc_pr_id: int | None = None
    team_id: int  # 채택된 Charter 규칙 조회용 — 기존 api_contract.md에 없던 필드, 협업 규칙 위반 검토에 필수라 추가
    trigger_type: TriggerType
    requested_by: UUID  # auto 호출(BE) 시에도 필수 — Doc PR 제출자의 userId (publicId)
    content: str  # 문서 본문 — 기존 api_contract.md에 없던 필드, AI가 BE DB를 직접 조회하지 않으므로 필수


class ReviewIssue(CamelModel):
    severity: Severity
    issue_type: IssueType
    description: str
    related_document_id: int | None = None
    charter_rule_id: UUID | None = None
    location_ref: str | None = None


class ReviewResponse(CamelModel):
    review_id: UUID
    overall_verdict: Verdict
    issues: list[ReviewIssue]
