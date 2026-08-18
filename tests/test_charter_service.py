from unittest.mock import MagicMock
from uuid import uuid4

from app.services.charter import (
    LLMCharterRule,
    adopt_rules,
    create_draft_rules,
    get_rule,
    list_rules,
    update_rule,
)


class TestCreateDraftRules:
    def test_persists_one_row_per_llm_rule_as_draft(self):
        db = MagicMock()
        team_id = 1
        llm_rules = [
            LLMCharterRule(title="리뷰 SLA", description="24시간 이내 리뷰"),
            LLMCharterRule(title="소통 채널", description="슬랙 #urgent"),
        ]

        rows = create_draft_rules(db, team_id, llm_rules)

        assert len(rows) == 2
        assert all(row.team_ref == team_id for row in rows)
        assert all(row.status == "draft" for row in rows)
        assert all(row.generated_by == "ai" for row in rows)
        assert rows[0].title == "리뷰 SLA"
        db.add_all.assert_called_once_with(rows)
        db.commit.assert_called_once()


class TestGetRule:
    def test_returns_row_by_id(self):
        db = MagicMock()
        expected = MagicMock()
        db.get.return_value = expected
        rule_id = uuid4()

        result = get_rule(db, rule_id)

        assert result is expected
        db.get.assert_called_once()


class TestUpdateRule:
    def test_updates_title_and_description_and_commits(self):
        db = MagicMock()
        rule = MagicMock()

        result = update_rule(db, rule, "새 제목", "새 설명")

        assert result is rule
        assert rule.title == "새 제목"
        assert rule.description == "새 설명"
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(rule)


class TestAdoptRules:
    def test_bulk_updates_status_and_commits(self):
        db = MagicMock()
        team_id = 1
        rule_ids = [uuid4(), uuid4()]
        adopted_by = uuid4()

        adopt_rules(db, team_id, rule_ids, adopted_by)

        update_call = db.query.return_value.filter.return_value.update
        update_call.assert_called_once()
        update_values = update_call.call_args[0][0]
        assert update_values["status"] == "adopted"
        assert update_values["adopted_by_ref"] == adopted_by
        assert "adopted_at" in update_values
        db.commit.assert_called_once()


class TestListRules:
    def test_filters_by_team_id_only_when_status_not_given(self):
        db = MagicMock()
        team_id = 1
        expected = [MagicMock()]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = expected

        result = list_rules(db, team_id)

        assert result == expected
        db.query.return_value.filter.assert_called_once()

    def test_filters_by_status_when_given(self):
        db = MagicMock()
        team_id = 1
        chained_filter = db.query.return_value.filter.return_value.filter
        chained_filter.return_value.order_by.return_value.all.return_value = []

        list_rules(db, team_id, status="draft")

        chained_filter.assert_called_once()
