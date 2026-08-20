"""locationRef 포맷 — {"blockId", "quote"} JSON.

blockId만으로는 "이 문단에 문제 있음"까지만 짚힌다. 문단이 길면 쓸모가 떨어지므로
인용문을 함께 담아 블록 안에서 위치를 좁힌다.
"""

import json

from app.services.document_lion import LLMReviewIssue, build_location_ref, parse_location_ref


def _issue(**overrides):
    base = {"severity": "minor", "issue_type": "charter_violation", "description": "위반"}
    base.update(overrides)
    return LLMReviewIssue(**base)


class TestBuildLocationRef:
    def test_keeps_block_id_present_in_document(self):
        result = build_location_ref(_issue(block_id="b-2", quote="문제 문장"), {"b-1", "b-2"})

        assert json.loads(result) == {"blockId": "b-2", "quote": "문제 문장"}

    def test_drops_hallucinated_block_id_but_keeps_quote(self):
        """LLM은 존재하지 않는 blockId를 만들어낸다.

        검증 없이 저장하면 FE가 없는 블록을 찾다 조용히 실패한다. 인용문은 살려둔다 —
        위치를 정확히 못 짚어도 어느 문장이 문제인지는 전달된다.
        """
        result = build_location_ref(_issue(block_id="b-99", quote="문제 문장"), {"b-1", "b-2"})

        assert json.loads(result) == {"quote": "문제 문장"}

    def test_drops_block_id_when_no_blocks_were_provided(self):
        """blocks를 안 받았으면 blockId를 검증할 수 없다 — 검증 불가한 값은 버린다."""
        assert json.loads(build_location_ref(_issue(block_id="b-1", quote="문장"), set())) == {"quote": "문장"}
        assert json.loads(build_location_ref(_issue(block_id="b-1", quote="문장"), None)) == {"quote": "문장"}

    def test_returns_none_when_nothing_usable(self):
        assert build_location_ref(_issue(), {"b-1"}) is None
        assert build_location_ref(_issue(block_id="b-99"), {"b-1"}) is None
        assert build_location_ref(_issue(quote="   "), {"b-1"}) is None

    def test_block_id_alone_is_kept(self):
        result = build_location_ref(_issue(block_id="b-1"), {"b-1"})

        assert json.loads(result) == {"blockId": "b-1"}


class TestParseLocationRef:
    def test_parses_stored_json(self):
        stored = json.dumps({"blockId": "b-1", "quote": "문장"})

        assert parse_location_ref(stored) == {"blockId": "b-1", "quote": "문장"}

    def test_none_passes_through(self):
        assert parse_location_ref(None) is None
        assert parse_location_ref("") is None

    def test_legacy_plain_text_becomes_quote(self):
        """포맷 확정 전에 저장된 행은 임의 문자열이다. 버리지 않고 인용문으로 살린다."""
        assert parse_location_ref("3번째 문단") == {"quote": "3번째 문단"}

    def test_json_that_is_not_an_object_becomes_quote(self):
        assert parse_location_ref("[1, 2]") == {"quote": "[1, 2]"}

    def test_unknown_keys_are_ignored(self):
        stored = json.dumps({"blockId": "b-1", "quote": "문장", "bogus": 1})

        assert parse_location_ref(stored) == {"blockId": "b-1", "quote": "문장"}
