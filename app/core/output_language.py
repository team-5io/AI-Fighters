"""AI 생성 텍스트의 출력 언어 지시문.

**AI는 항상 영어로 생성한다.** 사용자 언어로의 번역은 FE가 브라우저 온디바이스
번역으로 처리한다 (2026-08-21 결정). 그래서 서버에는 locale 개념이 없다.

지시문을 상수 하나로 두는 이유: 이 지시가 빠져서 실제로 버그가 났었다(PR #24 —
프롬프트에 출력 언어 지시가 없어 Gemini가 프롬프트 언어를 따라갔다). 세 서비스가
각자 문장을 적으면 한 곳이 빠지거나 표현이 갈라진다.
"""

OUTPUT_LANGUAGE_INSTRUCTION = "Write all natural-language output in English."
