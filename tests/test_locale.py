import logging

import pytest

from app.core.locale import (
    DEFAULT_LOCALE,
    FALLBACK_LOCALE,
    SUPPORTED_LOCALES,
    language_instruction,
    language_name,
    normalize_locale,
)


class TestNormalizeLocale:
    @pytest.mark.parametrize("raw", [None, "", "   ", "\t\n"])
    def test_missing_value_falls_back_to_default(self, raw):
        """locale 미전달은 하위 호환 — BE가 아직 안 붙은 구간의 현행 동작(한국어)을 유지한다."""
        assert normalize_locale(raw) == DEFAULT_LOCALE

    @pytest.mark.parametrize("raw", ["ko", "en", "ja"])
    def test_supported_value_passes_through(self, raw):
        assert normalize_locale(raw) == raw

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("KO", "ko"),
            ("ko-KR", "ko"),
            ("ko_KR", "ko"),
            ("  ja  ", "ja"),
            ("JA-JP", "ja"),
            ("en-US", "en"),
            ("EN_us", "en"),
        ],
    )
    def test_normalizes_case_and_region_subtag(self, raw, expected):
        """BE에 검증이 없어 'KO', 'ko-KR' 같은 변형이 실제로 유입될 수 있다."""
        assert normalize_locale(raw) == expected

    @pytest.mark.parametrize("raw", ["th", "zh-CN", "Korean", "asdf", "*", "123"])
    def test_unsupported_value_falls_back_to_english(self, raw):
        """미지원 locale은 422가 아니라 영어 폴백 — AI의 422는 BE에서 502로 보인다."""
        assert normalize_locale(raw) == FALLBACK_LOCALE

    def test_unsupported_value_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.core.locale"):
            normalize_locale("th")
        assert "th" in caplog.text

    def test_missing_value_does_not_log_warning(self, caplog):
        """미전달은 정상 경로다 — 경고로 로그를 오염시키지 않는다."""
        with caplog.at_level(logging.WARNING, logger="app.core.locale"):
            normalize_locale(None)
        assert caplog.text == ""

    def test_never_raises_for_any_string(self):
        """어떤 입력이 와도 지원 목록 안의 값으로 떨어져야 한다."""
        for raw in [None, "", "-", "_", "ko-", "-ko", "ko--KR", "한국어", "🇰🇷"]:
            assert normalize_locale(raw) in SUPPORTED_LOCALES


class TestLanguageInstruction:
    @pytest.mark.parametrize(
        ("locale", "expected_name"),
        [("ko", "Korean"), ("en", "English"), ("ja", "Japanese")],
    )
    def test_contains_english_language_name(self, locale, expected_name):
        """프롬프트가 영어 기반이라 언어명도 영어가 모델에게 가장 모호하지 않다."""
        assert expected_name in language_instruction(locale)

    def test_normalizes_input_defensively(self):
        """호출부가 정규화를 빠뜨려도 안전하게 동작해야 한다."""
        assert "Korean" in language_instruction("ko-KR")
        assert "English" in language_instruction("th")
        assert "Korean" in language_instruction(None)


class TestLanguageName:
    @pytest.mark.parametrize(
        ("locale", "expected"),
        [("ko", "Korean"), ("en", "English"), ("ja", "Japanese")],
    )
    def test_returns_english_language_name(self, locale, expected):
        assert language_name(locale) == expected

    def test_normalizes_input_defensively(self):
        assert language_name("JA_JP") == "Japanese"
        assert language_name(None) == "Korean"
