from typing import Literal
from uuid import UUID

from app.schemas.base import CamelModel

TriggerType = Literal["manual", "auto"]
Severity = Literal["critical", "medium", "minor"]
IssueType = Literal["conflict", "inconsistency", "charter_violation"]
Verdict = Literal["approve", "reject_recommended"]


class RelatedDocument(CamelModel):
    """BE가 GET /documents/{documentId}/relations로 찾은 이웃 문서.

    그 API 응답에는 본문이 없다(id·제목·관계유형·방향뿐). 검토를 하려면 본문이
    필요하므로 BE가 이웃 문서 본문까지 조회해 실어 보낸다. AI가 BE를 직접 호출하지
    않는 기존 구조(Charter 규칙·문서 본문과 동일)를 그대로 따른다.
    """

    document_id: int
    title: str
    content: str
    relation_type: str
    # 조회 기준 문서 대비 방향 (OUTGOING/INCOMING). BE가 이미 돌려주는 값이라 받아둔다.
    direction: str | None = None


class DocumentBlock(CamelModel):
    block_id: str
    content: str


class LocationRef(CamelModel):
    """이슈 위치. blockId로 블록을 찾고 quote로 블록 안 위치를 좁힌다.

    quote는 번역하지 않는다 — 원문 문서를 가리키는 포인터이기 때문이다. 일본 사용자가
    조회하면 설명은 일본어인데 quote만 원문 언어로 남는다. 이것이 정상 동작이다.
    """

    block_id: str | None = None
    quote: str | None = None


class ReviewRequest(CamelModel):
    document_id: int
    doc_pr_id: int | None = None
    team_id: int  # 채택된 Charter 규칙 조회용 — 기존 api_contract.md에 없던 필드, 협업 규칙 위반 검토에 필수라 추가
    trigger_type: TriggerType
    requested_by: UUID  # auto 호출(BE) 시에도 필수 — Doc PR 제출자의 userId (publicId)
    content: str  # 문서 본문 — 기존 api_contract.md에 없던 필드, AI가 BE DB를 직접 조회하지 않으므로 필수
    # BE 사용자 프로필의 선호 언어. optional이다 — required로 잡으면 BE가 아직 locale을
    # 실어보내지 않는 구간의 모든 호출이 422가 되고, BE가 이를 502로 감싸 내려보낸다.
    locale: str | None = None
    # 문서를 블록 단위로 받으면 이슈 위치를 blockId로 정확히 짚을 수 있다.
    # locale과 같은 이유로 optional이다 — BE 미배포 구간에서 422가 나면 안 된다.
    blocks: list[DocumentBlock] | None = None
    # conflict/inconsistency 검토용. locale·blocks와 같은 이유로 optional이다.
    related_documents: list[RelatedDocument] | None = None


class ReviewIssue(CamelModel):
    severity: Severity
    issue_type: IssueType
    description: str
    related_document_id: int | None = None
    charter_rule_id: UUID | None = None
    location_ref: LocationRef | None = None


class ReviewResponse(CamelModel):
    review_id: UUID
    overall_verdict: Verdict
    issues: list[ReviewIssue]
