import json
from uuid import UUID

from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.locale import language_instruction
from app.models.charter_rule import CharterRule
from app.models.document_review import DocumentReview
from app.models.document_review_issue import DocumentReviewIssue
from app.schemas.document_lion import DocumentBlock
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
    # 위치는 blockId + 원문 인용으로 받는다. LLM에게 JSON 문자열을 만들게 하는 대신
    # 구조화된 필드로 받고 저장 직전에 우리가 직렬화한다.
    block_id: str | None = None
    quote: str | None = None


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


def build_location_ref(issue: LLMReviewIssue, valid_block_ids: set[str] | None) -> str | None:
    """이슈 위치를 저장용 JSON 문자열로 만든다.

    LLM은 존재하지 않는 block_id를 만들어낸다. 전달한 블록 집합에 없으면 버린다 —
    검증 없이 저장하면 FE가 없는 블록을 찾다 조용히 실패한다. 인용문은 살려둔다.
    """
    payload: dict[str, str] = {}

    block_id = (issue.block_id or "").strip()
    if block_id and valid_block_ids and block_id in valid_block_ids:
        payload["blockId"] = block_id

    quote = (issue.quote or "").strip()
    if quote:
        payload["quote"] = quote

    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False)


def parse_location_ref(raw: str | None) -> dict[str, str] | None:
    """저장된 location_ref를 응답용 dict로 되돌린다.

    포맷 확정 전에 저장된 행은 임의 문자열이다. 버리지 않고 인용문으로 살린다.
    """
    if raw is None or not raw.strip():
        return None

    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {"quote": raw}

    if not isinstance(data, dict):
        return {"quote": raw}

    parsed: dict[str, str] = {}
    for key in ("blockId", "quote"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            parsed[key] = value
    return parsed or None


def call_document_lion_llm(
    content: str,
    charter_rules: list[CharterRuleContext],
    locale: str | None = None,
    blocks: list[DocumentBlock] | None = None,
) -> LLMReviewResult:
    rules_text = "\n".join(f"- ({r.id}) {r.title}: {r.description}" for r in charter_rules) or "(채택된 협업 규칙 없음)"

    if blocks:
        # 협업 규칙 UUID를 되돌려받는 것과 같은 기법 — 식별자를 프롬프트에 노출하고 그대로 인용하게 한다.
        document_text = "\n".join(f"[{b.block_id}] {b.content}" for b in blocks)
        location_instruction = (
            "문서는 [block_id] 접두사가 붙은 블록 단위로 주어진다. 각 issue에는 문제가 있는 "
            "블록의 block_id를 접두사에 있는 값 그대로 넣고, quote에는 문제가 되는 문장을 "
            "원문에서 그대로 발췌해 넣어라. 문서에 없는 block_id를 새로 만들지 마라.\n"
        )
    else:
        document_text = content
        location_instruction = "각 issue의 quote에는 문제가 되는 문장을 원문에서 그대로 발췌해 넣어라.\n"

    prompt = (
        "다음 문서 내용을 검토해서 문제가 있으면 issue로 보고해라.\n"
        "아래 팀 협업 규칙(Charter)을 위반하는 내용이 있으면 issue_type을 'charter_violation'으로, "
        "심각도(severity: 'critical'/'medium'/'minor')와 함께 보고해라. "
        "위반한 규칙이 명확하면 charter_rule_id에 해당 규칙의 괄호 안 UUID를 그대로 넣어라. "
        "문제가 없으면 issues를 빈 배열로 반환해라.\n"
        f"{location_instruction}"
        "\n"
        f"{language_instruction(locale)}\n\n"
        f"협업 규칙:\n{rules_text}\n\n"
        f"문서 내용:\n{document_text}"
    )
    response = get_genai_client().models.generate_content(
        model=settings.effective_document_lion_model,
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
    valid_block_ids: set[str] | None = None,
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
            location_ref=build_location_ref(issue, valid_block_ids),
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
