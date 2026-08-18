from unittest.mock import MagicMock
from uuid import uuid4

from app.services.document_lion import (
    LLMReviewIssue,
    create_review,
    fetch_adopted_charter_rules,
    get_review,
)


class TestFetchAdoptedCharterRules:
    def test_filters_by_team_and_adopted_status(self):
        db = MagicMock()
        team_id = 1
        expected = [MagicMock()]
        db.query.return_value.filter.return_value.all.return_value = expected

        result = fetch_adopted_charter_rules(db, team_id)

        assert result == expected
        db.query.return_value.filter.assert_called_once()


class TestCreateReview:
    def test_approve_when_no_critical_issues(self):
        db = MagicMock()
        document_id = 100
        requested_by = uuid4()
        llm_issues = [LLMReviewIssue(severity="minor", issue_type="charter_violation", description="사소한 위반")]

        review, issues = create_review(db, document_id, None, "manual", requested_by, llm_issues)

        assert review.overall_verdict == "approve"
        assert review.document_ref == document_id
        assert review.requested_by_ref == requested_by
        assert len(issues) == 1
        assert issues[0].description == "사소한 위반"
        db.add.assert_called_once_with(review)
        db.add_all.assert_called_once_with(issues)
        db.commit.assert_called_once()

    def test_reject_recommended_when_any_critical_issue(self):
        db = MagicMock()
        llm_issues = [
            LLMReviewIssue(severity="minor", issue_type="charter_violation", description="사소한 위반"),
            LLMReviewIssue(severity="critical", issue_type="charter_violation", description="심각한 위반"),
        ]

        review, _ = create_review(db, 100, 7, "auto", uuid4(), llm_issues)

        assert review.overall_verdict == "reject_recommended"

    def test_no_issues_means_approve_and_empty_list(self):
        db = MagicMock()

        review, issues = create_review(db, 100, None, "manual", uuid4(), [])

        assert review.overall_verdict == "approve"
        assert issues == []


class TestGetReview:
    def test_returns_review_and_its_issues(self):
        db = MagicMock()
        review_id = uuid4()
        fake_review = MagicMock()
        fake_issues = [MagicMock()]
        db.get.return_value = fake_review
        db.query.return_value.filter.return_value.all.return_value = fake_issues

        result = get_review(db, review_id)

        assert result == (fake_review, fake_issues)

    def test_returns_none_when_review_not_found(self):
        db = MagicMock()
        db.get.return_value = None

        result = get_review(db, uuid4())

        assert result is None
