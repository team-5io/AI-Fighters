"""AI 생성 텍스트의 출력 언어(locale) 처리를 한곳으로 모은다.

세 서비스(writing_assistant / charter / document_lion)가 각자 언어 지시 문자열을
조립하면 표현이 세 벌로 갈라진다. 지원 언어 목록과 지시문 형식을 이 모듈이 단독으로 소유한다.
"""

import logging

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = frozenset({"ko", "en", "ja"})

# locale 미전달 시 — 하위 호환. BE가 locale을 실어보내기 전 구간에서도 현행 동작(한국어)이 유지된다.
DEFAULT_LOCALE = "ko"

# 지원하지 않는 값이 왔을 때 — 한국어보다 범용적이다.
FALLBACK_LOCALE = "en"

_LANGUAGE_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese"}


def normalize_locale(raw: str | None) -> str:
    """요청에서 받은 locale을 지원 언어 중 하나로 정규화한다.

    BE `UpdateProfileRequest.language`에 검증이 없어 "KO", "ko-KR", "Korean" 같은 임의
    문자열이 실제로 유입될 수 있다. 그래서 거부하지 않고 관대하게 흡수한다.

    422를 내지 않는 것이 이 함수의 계약이다. AI가 422를 내면 BE가 502로 감싸 내려보내
    화면에는 "AI 장애"로 보인다. 어떤 입력이 와도 SUPPORTED_LOCALES 안의 값으로 떨어진다.
    """
    if raw is None or not raw.strip():
        return DEFAULT_LOCALE

    # "ko_KR" / "ko-KR" / "KO" -> "ko" (지역 서브태그 제거)
    primary = raw.strip().lower().replace("_", "-").split("-", 1)[0]

    if primary in SUPPORTED_LOCALES:
        return primary

    logger.warning("unsupported locale %r — falling back to %r", raw, FALLBACK_LOCALE)
    return FALLBACK_LOCALE


def language_instruction(raw: str | None) -> str:
    """프롬프트에 붙일 출력 언어 지시문을 만든다.

    호출부가 정규화를 빠뜨려도 안전하도록 내부에서 다시 정규화한다.
    """
    return f"Write all natural-language output in {language_name(raw)}."


def language_name(raw: str | None) -> str:
    """번역 프롬프트 및 지시문에 쓸 영어 언어명을 돌려준다.

    언어명을 영어로 쓰는 이유: 기존 프롬프트가 영어 기반이고, 영어 언어명이 모델에게
    가장 모호하지 않다.
    """
    return _LANGUAGE_NAMES[normalize_locale(raw)]
