import hashlib
import json
from unittest.mock import MagicMock

from app.services.translation import (
    deserialize_preserved_terms,
    get_cached_translation,
    save_translation,
)


class TestGetCachedTranslation:
    def test_returns_query_result(self):
        db = MagicMock()
        expected = MagicMock()
        db.query.return_value.filter.return_value.one_or_none.return_value = expected
        document_id = 42

        result = get_cached_translation(db, document_id, "block-1", "en")

        assert result is expected
        db.query.return_value.filter.return_value.one_or_none.assert_called_once()

    def test_returns_none_when_no_cache_hit(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.one_or_none.return_value = None

        result = get_cached_translation(db, 42, "block-1", "en")

        assert result is None


class TestSaveTranslation:
    def test_persists_row_with_expected_fields(self):
        db = MagicMock()
        document_id = 42
        block_id = "block-1"
        content = "안녕하세요"
        preserved_terms = ["Doc PR", "RACI"]

        row = save_translation(
            db,
            document_id=document_id,
            block_id=block_id,
            source_lang="ko",
            target_lang="en",
            content=content,
            translated_content="Hello",
            preserved_terms=preserved_terms,
        )

        assert row.document_ref == document_id
        assert row.block_ref == block_id
        assert row.source_lang == "ko"
        assert row.target_lang == "en"
        assert row.translated_content == "Hello"
        assert row.preserved_terms == json.dumps(preserved_terms, ensure_ascii=False)
        assert row.source_content_hash == hashlib.sha256(content.encode("utf-8")).hexdigest()

    def test_commits_and_refreshes(self):
        db = MagicMock()

        row = save_translation(
            db,
            document_id=42,
            block_id="block-1",
            source_lang="ko",
            target_lang="en",
            content="content",
            translated_content="translated",
            preserved_terms=[],
        )

        db.add.assert_called_once_with(row)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(row)

    def test_empty_preserved_terms_serializes_to_empty_list(self):
        db = MagicMock()

        row = save_translation(
            db,
            document_id=42,
            block_id="block-1",
            source_lang="ko",
            target_lang="en",
            content="content",
            translated_content="translated",
            preserved_terms=[],
        )

        assert row.preserved_terms == "[]"


class TestDeserializePreservedTerms:
    def test_none_returns_empty_list(self):
        assert deserialize_preserved_terms(None) == []

    def test_empty_string_returns_empty_list(self):
        assert deserialize_preserved_terms("") == []

    def test_parses_json_array(self):
        raw = json.dumps(["Doc PR", "RACI"], ensure_ascii=False)
        assert deserialize_preserved_terms(raw) == ["Doc PR", "RACI"]
