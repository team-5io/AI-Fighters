"""저장 시점에 원본 언어를 기록한다.

이 값이 비어 있으면 나중에 조회할 때 무슨 언어에서 번역해야 하는지 알 수 없어
번역 자체가 불가능하다.
"""

from unittest.mock import MagicMock
from uuid import uuid4

from app.services.charter import LLMCharterRule, create_draft_rules, update_rule
from app.services.document_lion import LLMReviewIssue, create_review


class TestCharterRuleSourceLocale:
    def test_defaults_to_korean(self):
        rows = create_draft_rules(MagicMock(), 1, [LLMCharterRule(title="t", description="d")])

        assert rows[0].source_locale == "ko"

    def test_stores_requested_locale(self):
        rows = create_draft_rules(MagicMock(), 1, [LLMCharterRule(title="t", description="d")], locale="ja")

        assert rows[0].source_locale == "ja"

    def test_normalizes_locale_before_storing(self):
        """BE에 검증이 없어 'ko-KR' 같은 변형이 들어올 수 있다. 저장값은 정규화된 코드여야 한다."""
        rows = create_draft_rules(MagicMock(), 1, [LLMCharterRule(title="t", description="d")], locale="JA-JP")

        assert rows[0].source_locale == "ja"


class TestUpdateRuleSourceLocale:
    def test_updates_source_locale_when_given(self):
        """일본 사용자가 한국어 규칙을 일본어로 고쳐 쓸 수 있다 — 원본 언어도 함께 바뀐다."""
        rule = MagicMock()
        rule.source_locale = "ko"

        update_rule(MagicMock(), rule, "새 제목", "새 설명", locale="ja")

        assert rule.source_locale == "ja"

    def test_keeps_source_locale_when_locale_omitted(self):
        """locale 미전달 시 기존 원본 언어를 덮어쓰지 않는다 — BE 미배포 구간 보호."""
        rule = MagicMock()
        rule.source_locale = "ja"

        update_rule(MagicMock(), rule, "새 제목", "새 설명")

        assert rule.source_locale == "ja"


class TestDocumentReviewSourceLocale:
    def _issues(self):
        return [LLMReviewIssue(severity="minor", issue_type="charter_violation", description="위반")]

    def test_defaults_to_korean(self):
        review, _ = create_review(MagicMock(), 100, None, "manual", uuid4(), self._issues())

        assert review.source_locale == "ko"

    def test_stores_requested_locale(self):
        review, _ = create_review(MagicMock(), 100, None, "manual", uuid4(), self._issues(), locale="ja")

        assert review.source_locale == "ja"

    def test_issues_inherit_parent_locale(self):
        """한 리뷰의 이슈들은 단일 LLM 호출로 생성되므로 언어가 항상 같다 —
        칸은 부모(document_review)에만 둔다."""
        review, issues = create_review(MagicMock(), 100, None, "manual", uuid4(), self._issues(), locale="ja")

        assert review.source_locale == "ja"
        assert not hasattr(issues[0], "source_locale") or issues[0].source_locale is None
