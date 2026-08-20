"""연관 문서 기반 conflict/inconsistency 검토.

BE의 GET /documents/{documentId}/relations는 이웃 문서의 id·제목·관계유형만 돌려주고
본문은 주지 않는다. 그래서 BE가 이웃 문서 본문까지 조회해 relatedDocuments로 실어 보낸다.
AI가 BE를 직접 호출하지 않는 기존 구조(Charter 규칙·문서 본문과 동일)를 그대로 따른다.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.document_lion import (
    LLMReviewIssue,
    LLMReviewResult,
    RelatedDocumentContext,
    call_document_lion_llm,
    create_review,
)


def _ctx(doc_id=200, title="보안 정책 문서", content="비밀번호는 90일마다 교체한다", relation_type="REFERENCE"):
    return RelatedDocumentContext(
        id=doc_id, title=title, content=content, relation_type=relation_type, direction="OUTGOING"
    )


def _mock_empty(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=LLMReviewResult(issues=[]))
    mock_get_client.return_value = mock_client
    return mock_client


class TestPrompt:
    @patch("app.services.document_lion.get_genai_client")
    def test_renders_related_documents_with_ids(self, mock_get_client):
        mock_client = _mock_empty(mock_get_client)

        call_document_lion_llm("본문", [], related_documents=[_ctx()])

        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "(200" in prompt
        assert "보안 정책 문서" in prompt
        assert "비밀번호는 90일마다 교체한다" in prompt
        assert "REFERENCE" in prompt

    @patch("app.services.document_lion.get_genai_client")
    def test_instructs_conflict_and_inconsistency(self, mock_get_client):
        mock_client = _mock_empty(mock_get_client)

        call_document_lion_llm("본문", [], related_documents=[_ctx()])

        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "inconsistency" in prompt
        assert "conflict" in prompt
        assert "related_document_id" in prompt

    @patch("app.services.document_lion.get_genai_client")
    def test_absent_related_documents_keeps_working(self, mock_get_client):
        """relatedDocuments는 optional이다 — BE 미배포 구간에서 422가 나면 안 된다."""
        mock_client = _mock_empty(mock_get_client)

        call_document_lion_llm("본문", [])

        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "연관 문서 없음" in prompt

    @patch("app.services.document_lion.get_genai_client")
    def test_empty_list_is_treated_as_absent(self, mock_get_client):
        mock_client = _mock_empty(mock_get_client)

        call_document_lion_llm("본문", [], related_documents=[])

        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        assert "연관 문서 없음" in prompt


class TestHallucinationGuard:
    def _issue(self, related_document_id):
        return LLMReviewIssue(
            severity="medium",
            issue_type="inconsistency",
            description="연관 문서와 교체 주기가 다르다",
            related_document_id=related_document_id,
        )

    def test_keeps_id_present_in_request(self):
        _, issues = create_review(
            MagicMock(), 100, None, "manual", uuid4(), [self._issue(200)], valid_related_document_ids={200, 300}
        )

        assert issues[0].related_document_ref == 200

    def test_drops_hallucinated_id(self):
        """LLM은 존재하지 않는 문서 id를 만들어낸다. blockId와 같은 방어를 적용한다."""
        _, issues = create_review(
            MagicMock(), 100, None, "manual", uuid4(), [self._issue(999)], valid_related_document_ids={200}
        )

        assert issues[0].related_document_ref is None

    def test_drops_id_when_no_related_documents_were_provided(self):
        """연관 문서를 안 받았으면 id를 검증할 수 없다 — 검증 불가한 값은 버린다."""
        _, issues = create_review(MagicMock(), 100, None, "manual", uuid4(), [self._issue(200)])

        assert issues[0].related_document_ref is None

    def test_none_stays_none(self):
        _, issues = create_review(
            MagicMock(), 100, None, "manual", uuid4(), [self._issue(None)], valid_related_document_ids={200}
        )

        assert issues[0].related_document_ref is None

    def test_charter_violation_issue_is_unaffected(self):
        issue = LLMReviewIssue(severity="critical", issue_type="charter_violation", description="위반")

        review, issues = create_review(MagicMock(), 100, None, "manual", uuid4(), [issue])

        assert review.overall_verdict == "reject_recommended"
        assert issues[0].related_document_ref is None
