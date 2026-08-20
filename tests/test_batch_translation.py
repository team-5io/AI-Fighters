"""배치 번역 — 여러 텍스트를 1회 LLM 호출로 번역한다.

청크 분할은 토큰 대책이기도 하지만 본질은 실패 격리다. 응답 개수가 어긋나면 그 묶음
전체를 원문으로 되돌려야 하는데, 한 번에 다 보내면 하나 때문에 전부 원문이 된다.
"""

import logging
from unittest.mock import MagicMock, patch

from app.services.translation import (
    LLMBatchTranslationResult,
    call_batch_translation_llm,
    chunk_indices,
)


class TestChunkIndices:
    def test_empty_input(self):
        assert chunk_indices([], 100) == []

    def test_fits_in_one_chunk(self):
        assert chunk_indices(["a" * 30, "b" * 30], 100) == [[0, 1]]

    def test_exact_boundary_stays_in_one_chunk(self):
        assert chunk_indices(["a" * 50, "b" * 50], 100) == [[0, 1]]

    def test_splits_when_exceeding(self):
        assert chunk_indices(["a" * 60, "b" * 60], 100) == [[0], [1]]

    def test_single_oversized_item_gets_its_own_chunk(self):
        """항목 하나가 한도를 넘으면 혼자 한 청크가 된다 — 안 정해두면 빈 청크나 무한 루프가 난다."""
        assert chunk_indices(["a" * 500], 100) == [[0]]

    def test_oversized_item_in_the_middle(self):
        result = chunk_indices(["a" * 10, "b" * 500, "c" * 10], 100)

        assert result == [[0], [1], [2]]

    def test_every_index_appears_exactly_once(self):
        texts = ["x" * n for n in (10, 200, 30, 40, 500, 5)]
        flat = [i for chunk in chunk_indices(texts, 100) for i in chunk]

        assert sorted(flat) == list(range(len(texts)))


def _client(results):
    """results: generate_content 호출마다 돌려줄 parsed 값 목록 (예외 객체면 raise)."""
    mock_client = MagicMock()

    def side_effect(*args, **kwargs):
        value = results.pop(0)
        if isinstance(value, Exception):
            raise value
        return MagicMock(parsed=value)

    mock_client.models.generate_content.side_effect = side_effect
    return mock_client


class TestCallBatchTranslationLlm:
    @patch("app.services.translation.get_genai_client")
    def test_returns_translations_in_order(self, mock_get_client):
        mock_get_client.return_value = _client([LLMBatchTranslationResult(translations=["A", "B"])])

        result = call_batch_translation_llm(["가", "나"], "ko", "en")

        assert result == ["A", "B"]

    @patch("app.services.translation.get_genai_client")
    def test_empty_input_does_not_call_llm(self, mock_get_client):
        mock_client = _client([])
        mock_get_client.return_value = mock_client

        assert call_batch_translation_llm([], "ko", "en") == []
        mock_client.models.generate_content.assert_not_called()

    @patch("app.services.translation.get_genai_client")
    def test_length_mismatch_falls_back_to_source(self, mock_get_client, caplog):
        """순서가 어긋난 채 매핑되면 엉뚱한 규칙에 엉뚱한 번역이 붙는다. 실패로 간주한다."""
        mock_get_client.return_value = _client([LLMBatchTranslationResult(translations=["A"])])

        with caplog.at_level(logging.WARNING, logger="app.services.translation"):
            result = call_batch_translation_llm(["가", "나"], "ko", "en")

        assert result == ["가", "나"]
        assert caplog.text

    @patch("app.services.translation.get_genai_client")
    def test_llm_failure_falls_back_to_source(self, mock_get_client):
        """번역 실패 시 예외를 전파하지 않는다 — 조회 화면이 통째로 죽는 것보다 원문이 낫다."""
        mock_get_client.return_value = _client([RuntimeError("boom")])

        assert call_batch_translation_llm(["가", "나"], "ko", "en") == ["가", "나"]

    @patch("app.services.translation.get_genai_client")
    def test_malformed_response_falls_back_to_source(self, mock_get_client):
        mock_get_client.return_value = _client([None])

        assert call_batch_translation_llm(["가"], "ko", "en") == ["가"]

    @patch("app.services.translation.get_genai_client")
    def test_failure_is_isolated_to_its_chunk(self, mock_get_client, monkeypatch):
        """청크 하나가 실패해도 나머지 청크의 번역은 살아남는다."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "translation_batch_chunk_chars", 10)
        mock_get_client.return_value = _client(
            [
                RuntimeError("첫 청크 실패"),
                LLMBatchTranslationResult(translations=["B"]),
            ]
        )

        result = call_batch_translation_llm(["가" * 10, "나" * 10], "ko", "en")

        assert result == ["가" * 10, "B"]

    @patch("app.services.translation.get_genai_client")
    def test_splits_into_multiple_llm_calls(self, mock_get_client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "translation_batch_chunk_chars", 10)
        mock_client = _client(
            [
                LLMBatchTranslationResult(translations=["A"]),
                LLMBatchTranslationResult(translations=["B"]),
            ]
        )
        mock_get_client.return_value = mock_client

        result = call_batch_translation_llm(["가" * 10, "나" * 10], "ko", "en")

        assert result == ["A", "B"]
        assert mock_client.models.generate_content.call_count == 2

    @patch("app.services.translation.get_genai_client")
    def test_prompt_asks_to_preserve_domain_terms(self, mock_get_client):
        """규칙·이슈 응답 스펙에 preservedTerms 필드는 없지만, 고유명사 원문 유지 지시는 넣는다."""
        mock_get_client.return_value = _client([LLMBatchTranslationResult(translations=["A"])])

        call_batch_translation_llm(["가"], "ko", "ja")

        prompt = mock_get_client.return_value.models.generate_content.call_args.kwargs["contents"]
        assert "Doc PR" in prompt
        assert "Korean" in prompt
        assert "Japanese" in prompt
