"""저장된 AI 텍스트를 조회 시점에 번역한다.

한국인이 만든 규칙을 나중에 합류한 일본 사용자가 조회하면 한국어가 그대로 노출된다.
이미 굳은 텍스트라 생성 시점에는 개입할 지점이 없다.

번역은 최초 조회 시 lazy로 수행하고 캐시한다 — 아무도 읽지 않는 언어에 쿼터를 쓰지 않는다.
"""

import hashlib
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.ai_text_translation import TranslatableField, translate_fields


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _field(text="리뷰는 24시간 이내", source_locale="ko", field="description", entity_id=None):
    return TranslatableField(
        entity_type="charter_rule",
        entity_id=entity_id or uuid4(),
        field=field,
        source_locale=source_locale,
        text=text,
    )


def _cache_row(field_obj, translated, source_text=None, target_locale="ja"):
    row = MagicMock()
    row.entity_type = field_obj.entity_type
    row.entity_id = field_obj.entity_id
    row.field = field_obj.field
    row.target_locale = target_locale
    row.translated_text = translated
    row.source_text_hash = _hash(source_text if source_text is not None else field_obj.text)
    return row


def _db(rows=()):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = list(rows)
    return db


@patch("app.services.ai_text_translation.call_batch_translation_llm")
class TestTranslateFields:
    def test_empty_input_does_nothing(self, mock_llm):
        assert translate_fields(_db(), [], "ja") == {}
        mock_llm.assert_not_called()

    def test_same_locale_needs_no_translation(self, mock_llm):
        """source_locale과 요청 locale이 같으면 LLM을 부르지 않는다."""
        f = _field(source_locale="ja")

        result = translate_fields(_db(), [f], "ja")

        assert result[(f.entity_id, f.field)] == f.text
        mock_llm.assert_not_called()

    def test_cache_hit_skips_llm(self, mock_llm):
        f = _field()
        db = _db([_cache_row(f, "レビューは24時間以内")])

        result = translate_fields(db, [f], "ja")

        assert result[(f.entity_id, f.field)] == "レビューは24時間以内"
        mock_llm.assert_not_called()

    def test_stale_hash_triggers_retranslation(self, mock_llm):
        """원문이 수정되면 저장된 번역은 거짓이 된다 — 해시가 다르면 재번역한다."""
        f = _field(text="리뷰는 48시간 이내")
        stale = _cache_row(f, "レビューは24時間以内", source_text="리뷰는 24시간 이내")
        db = _db([stale])
        mock_llm.return_value = ["レビューは48時間以内"]

        result = translate_fields(db, [f], "ja")

        assert result[(f.entity_id, f.field)] == "レビューは48時間以内"
        mock_llm.assert_called_once()
        # 기존 행을 갱신한다 — 유니크 제약이 있으므로 새로 넣으면 충돌한다
        assert stale.translated_text == "レビューは48時間以内"
        assert stale.source_text_hash == _hash(f.text)
        db.add.assert_not_called()

    def test_cache_miss_translates_and_stores(self, mock_llm):
        f = _field()
        db = _db()
        mock_llm.return_value = ["レビューは24時間以内"]

        result = translate_fields(db, [f], "ja")

        assert result[(f.entity_id, f.field)] == "レビューは24時間以内"
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_groups_by_source_locale(self, mock_llm):
        """원본 언어가 섞여 있으면 언어별로 묶어 각 묶음당 1회 호출한다."""
        ko = _field(text="한국어 규칙", source_locale="ko")
        en = _field(text="English rule", source_locale="en")
        mock_llm.side_effect = [["韓国語ルール"], ["英語ルール"]]

        result = translate_fields(_db(), [ko, en], "ja")

        assert mock_llm.call_count == 2
        assert result[(ko.entity_id, ko.field)] == "韓国語ルール"
        assert result[(en.entity_id, en.field)] == "英語ルール"

    def test_single_llm_call_for_multiple_fields_of_same_locale(self, mock_llm):
        entity = uuid4()
        title = _field(text="리뷰 SLA", field="title", entity_id=entity)
        desc = _field(text="24시간 이내", field="description", entity_id=entity)
        mock_llm.return_value = ["レビューSLA", "24時間以内"]

        result = translate_fields(_db(), [title, desc], "ja")

        mock_llm.assert_called_once()
        assert result[(entity, "title")] == "レビューSLA"
        assert result[(entity, "description")] == "24時間以内"

    def test_failed_translation_returns_source_and_is_not_cached(self, mock_llm):
        """번역 실패 시 call_batch_translation_llm은 원문을 되돌려준다.

        그 원문을 번역으로 저장하면 캐시가 영구히 오염되어 이후 재시도조차 하지 않는다.
        """
        f = _field()
        db = _db()
        mock_llm.return_value = [f.text]

        result = translate_fields(db, [f], "ja")

        assert result[(f.entity_id, f.field)] == f.text
        db.add.assert_not_called()

    def test_blank_text_is_skipped(self, mock_llm):
        f = _field(text="   ")

        result = translate_fields(_db(), [f], "ja")

        assert result[(f.entity_id, f.field)] == "   "
        mock_llm.assert_not_called()

    def test_unsupported_target_locale_is_normalized(self, mock_llm):
        """'th' 같은 미지원 locale은 영어로 폴백된다 — 422를 내지 않는다."""
        f = _field(source_locale="en")

        result = translate_fields(_db(), [f], "th")

        # en -> en 이 되어 번역이 불필요해진다
        assert result[(f.entity_id, f.field)] == f.text
        mock_llm.assert_not_called()
