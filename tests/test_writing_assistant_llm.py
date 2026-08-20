from unittest.mock import MagicMock, patch

import pytest

from app.services.writing_assistant import LLMSuggestion, LLMSuggestionsResult, call_writing_assistant_llm


@patch("app.services.writing_assistant.get_genai_client")
def test_returns_suggestions_from_llm(mock_get_client):
    parsed = LLMSuggestionsResult(
        suggestions=[
            LLMSuggestion(type="structure", text="섹션을 나누세요"),
            LLMSuggestion(type="clarity", text="이 문장을 더 명확하게 쓰세요"),
            LLMSuggestion(type="next-paragraph", text="다음엔 결론을 쓰세요"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_writing_assistant_llm("본문 내용", "커서 주변 문맥")

    # LLM 응답 순서(structure, clarity, next-paragraph)가 아니라
    # 표시 순서(structure -> next-paragraph -> clarity)로 정돈되어 나온다.
    assert [s.type for s in result] == ["structure", "next-paragraph", "clarity"]
    assert sorted(s.text for s in result) == sorted(s.text for s in parsed.suggestions)
    mock_client.models.generate_content.assert_called_once()


@patch("app.services.writing_assistant.get_genai_client")
def test_structure_suggestion_prompt_asks_for_toc_and_required_sections(mock_get_client):
    """Notion 기능명세서 "문서 구조 가이드 제안": 목차·필수 섹션 구조를 추천해야 한다."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=LLMSuggestionsResult(suggestions=[]))
    mock_get_client.return_value = mock_client

    call_writing_assistant_llm("본문 내용", "커서 주변 문맥")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "목차" in prompt
    assert "필수 섹션" in prompt


@patch("app.services.writing_assistant.get_genai_client")
def test_truncates_to_configured_count(mock_get_client):
    parsed = LLMSuggestionsResult(
        suggestions=[
            LLMSuggestion(type="structure", text="1"),
            LLMSuggestion(type="clarity", text="2"),
            LLMSuggestion(type="next-paragraph", text="3"),
            LLMSuggestion(type="structure", text="4"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_writing_assistant_llm("본문 내용", "커서 주변 문맥", count=2)

    assert len(result) == 2
    assert result == parsed.suggestions[:2]


@patch("app.services.writing_assistant.get_genai_client")
def test_raises_on_malformed_response(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=None)
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        call_writing_assistant_llm("본문 내용", "커서 주변 문맥")


def _mock_empty(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=LLMSuggestionsResult(suggestions=[]))
    mock_get_client.return_value = mock_client
    return mock_client


@patch("app.services.writing_assistant.get_genai_client")
def test_prompt_defaults_to_korean_when_locale_missing(mock_get_client):
    """locale 미전달 시 기본값은 한국어.

    PR #24 이전에는 프롬프트에 출력 언어 지시가 아예 없어 영어로 응답했다. locale을
    도입한 뒤에도 '지시가 존재하고, 미전달 시 한국어'라는 성질은 유지되어야 한다.
    BE가 locale을 실어보내기 전 구간의 현행 동작이 이것이다.
    """
    mock_client = _mock_empty(mock_get_client)

    call_writing_assistant_llm("본문 내용", "커서 주변 문맥")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "Korean" in prompt


@patch("app.services.writing_assistant.get_genai_client")
def test_prompt_uses_requested_locale(mock_get_client):
    mock_client = _mock_empty(mock_get_client)

    call_writing_assistant_llm("본문 내용", "커서 주변 문맥", locale="ja")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "Japanese" in prompt
    assert "Korean" not in prompt


@patch("app.services.writing_assistant.get_genai_client")
def test_prompt_falls_back_to_english_for_unsupported_locale(mock_get_client):
    """미지원 locale은 422가 아니라 영어 폴백 — AI의 422는 BE에서 502로 보인다."""
    mock_client = _mock_empty(mock_get_client)

    call_writing_assistant_llm("본문 내용", "커서 주변 문맥", locale="th")

    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "English" in prompt


@patch("app.services.writing_assistant.get_genai_client")
def test_suggestions_sorted_by_type(mock_get_client):
    """structure -> next-paragraph -> clarity 순으로 정렬한다 (큰 단위에서 작은 단위로).

    프롬프트에 순서 지시가 없어 LLM 응답 순서는 매번 달라진다. 같은 문서에 두 번
    요청했을 때 UI에서 제안 순서가 뒤바뀌어 보이는 것을 막는다.
    """
    parsed = LLMSuggestionsResult(
        suggestions=[
            LLMSuggestion(type="clarity", text="c"),
            LLMSuggestion(type="next-paragraph", text="n"),
            LLMSuggestion(type="structure", text="s"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_writing_assistant_llm("본문 내용", "커서 주변 문맥", count=3)

    assert [s.text for s in result] == ["s", "n", "c"]


@patch("app.services.writing_assistant.get_genai_client")
def test_sorting_happens_after_truncation(mock_get_client):
    """정렬은 자르기 이후다.

    먼저 정렬하고 자르면 structure 제안만 남도록 편향된다. LLM이 고른 상위 N개를
    존중하고, 표시 순서만 정돈하는 것이 목적이다.
    """
    parsed = LLMSuggestionsResult(
        suggestions=[
            LLMSuggestion(type="clarity", text="1"),
            LLMSuggestion(type="clarity", text="2"),
            LLMSuggestion(type="structure", text="3"),
        ]
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parsed=parsed)
    mock_get_client.return_value = mock_client

    result = call_writing_assistant_llm("본문 내용", "커서 주변 문맥", count=2)

    # structure("3")는 잘려나갔으므로 등장하지 않는다. 같은 유형 안에서는 원래 순서 유지.
    assert [s.text for s in result] == ["1", "2"]
