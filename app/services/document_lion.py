from uuid import UUID

from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.charter_rule import CharterRule
from app.models.document_review import DocumentReview
from app.models.document_review_issue import DocumentReviewIssue
from app.services.llm_client import get_genai_client


class CharterRuleContext(BaseModel):
    id: UUID
    title: str
    description: str


class LLMReviewIssue(BaseModel):
    severity: str
    issue_type: str
    description: str
    charter_rule_id: UUID | None = None
    location_ref: str | None = None


class LLMReviewResult(BaseModel):
    issues: list[LLMReviewIssue]


def fetch_adopted_charter_rules(db: Session, team_id: int) -> list[CharterRule]:
    return (
        db.query(CharterRule)
        .filter(CharterRule.team_ref == team_id, CharterRule.status == "adopted")
        .all()
    )


def fetch_related_documents(document_id: int) -> list[dict]:
    # TODO: BE Document Graph 조회 API(GET /documents/{id}/graph)가 아직 시작 전 상태라
    # 연관 문서를 가져올 방법이 없다. API 준비되면 실제 연동으로 교체한다.
    # 그 전까지는 conflict/inconsistency 검토가 항상 이슈 없음으로 나온다.
    return []


def call_document_lion_llm(content: str, charter_rules: list[CharterRuleContext]) -> LLMReviewResult:
    rules_text = "\n".join(f"- ({r.id}) {r.title}: {r.description}" for r in charter_rules) or "(채택된 협업 규칙 없음)"
    prompt = (
        "다음 문서 내용을 검토해서 문제가 있으면 issue로 보고해라.\n"
        "아래 팀 협업 규칙(Charter)을 위반하는 내용이 있으면 issue_type을 'charter_violation'으로, "
        "심각도(severity: 'critical'/'medium'/'minor')와 함께 보고해라. "
        "위반한 규칙이 명확하면 charter_rule_id에 해당 규칙의 괄호 안 UUID를 그대로 넣어라. "
        "문제가 없으면 issues를 빈 배열로 반환해라.\n\n"
        f"협업 규칙:\n{rules_text}\n\n"
        f"문서 내용:\n{content}"
    )
    response = get_genai_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMReviewResult,
        ),
    )
    result = response.parsed
    if not isinstance(result, LLMReviewResult):
        raise RuntimeError("document_lion_review_failed: empty or malformed LLM response")
    return result


def create_review(
    db: Session,
    document_id: int,
    doc_pr_id: int | None,
    trigger_type: str,
    requested_by: UUID,
    llm_issues: list[LLMReviewIssue],
) -> tuple[DocumentReview, list[DocumentReviewIssue]]:
    overall_verdict = "reject_recommended" if any(issue.severity == "critical" for issue in llm_issues) else "approve"
    review = DocumentReview(
        doc_pr_ref=doc_pr_id,
        document_ref=document_id,
        trigger_type=trigger_type,
        overall_verdict=overall_verdict,
        requested_by_ref=requested_by,
    )
    db.add(review)
    db.flush()

    issue_rows = [
        DocumentReviewIssue(
            review_id=review.id,
            severity=issue.severity,
            issue_type=issue.issue_type,
            description=issue.description,
            charter_rule_id=issue.charter_rule_id,
            location_ref=issue.location_ref,
        )
        for issue in llm_issues
    ]
    db.add_all(issue_rows)
    db.commit()
    db.refresh(review)
    return review, issue_rows


def get_review(db: Session, review_id: UUID) -> tuple[DocumentReview, list[DocumentReviewIssue]] | None:
    review = db.get(DocumentReview, review_id)
    if review is None:
        return None
    issues = db.query(DocumentReviewIssue).filter(DocumentReviewIssue.review_id == review_id).all()
    return review, issues
