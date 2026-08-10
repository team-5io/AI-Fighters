# AI 파트 인수인계

담당: 김민섭 (AI)

## 버전 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.0.0 | 2026-08-10 | 최초 작성 — Translation 캐시 레이어 작업(#2, #3) 기준 |

## Done (v1.0.0 기준, 2026-08-10)

- `translation_cache` 캐시 조회/저장 서비스 레이어 추가 (`app/services/translation.py`)
  - documentId + targetLang 기준으로만 조회 (원문 해시로 캐시 무효화하는 로직은 넣지 않기로 결정)
- `/api/ai/translations` 라우터에 `Depends(get_db)` 연결 — 캐시 히트 시 실제 응답 반환하도록 수정 (캐시 미스는 여전히 501)
- `TranslationRequest.document_id` 타입이 `str`로 잘못 되어 있던 것을 `UUID`로 수정 (다른 스키마들과 통일)
- LLM 모델을 **Gemini 3.5 Flash-Lite**로 쓰기로 방향 잡음 (성민과 최종 확정 필요)
  - `requirements.txt`에 `google-genai==2.17.0` 추가
  - `app/core/config.py`, `.env.example`의 설정 필드를 `OPENAI_API_KEY`/`openai_api_key` → `GEMINI_API_KEY`/`gemini_api_key`로 변경
  - 로컬 `.env`에 `GEMINI_API_KEY=` 자리 생성 완료 (값은 본인이 직접 채워 넣기로 함, 아직 미입력)
- 이슈 [#2](https://github.com/team-5io/AI-Fighters/issues/2), PR [#3](https://github.com/team-5io/AI-Fighters/pull/3) 오픈 (`feature/ai-translation-cache` → `develop`, 리뷰 대기 중)

## Next (우선순위 순)

1. **Gemini API 키 발급 후 `.env`에 입력** — 이게 막혀 있어서 아래 작업들이 다 대기 상태
2. **PR #3 리뷰 확인 및 머지** — 머지 전까지 다른 작업은 이 브랜치 위가 아니라 develop 기준으로 새로 브랜치 따는 게 안전
3. **Translation LLM 연동** (`app/services/translation.py`)
   - `google-genai` 클라이언트로 실제 번역 호출 코드 작성, `save_translation()`으로 캐시 저장까지 연결
   - `app/api/routes/translation.py`의 501 자리를 실제 호출로 교체
   - 열린 질문 — 계약서(`docs/api_contract.md`) 기준 "번역 실패 시 재시도 버튼 없이 즉시 원문 표시"로 이미 확정되어 있으니 그대로 구현하면 됨
4. **Writing Assistant** (`app/api/routes/writing_assistant.py`, 스펙 F-NYSIWY) — Translation 다음 순서로 진행
   - 열린 질문 미확정: 제안 유형별 그룹핑 여부, 한 번에 내려줄 제안 개수 — 성민과 확정 필요 (API 응답 필드 자체는 이미 양쪽 다 가능하게 잡혀있음)
5. **DocumentLion** (`app/api/routes/document_lion.py`, 스펙 F-MLRHDJ)
   - 문서 정합성/Charter 위반 검토라 Translation·Writing Assistant보다 추론 난이도가 높음 — **Flash-Lite로 충분한지, 상위 모델(예: Gemini 3.1 Pro)이 필요한지 성민/팀과 논의 필요**
   - `locationRef` 포맷도 미확정 — FE 에디터가 문장/섹션을 식별하는 방식에 맞춰야 함

## 확인이 필요한 부분

- **DB에 실제 테이블이 생성되어 있는지 미확인.** 리포지토리에 alembic 등 마이그레이션 도구가 없다 — ERD Cloud로 만든 스키마를 BE(준한/재원)가 어떻게 DB에 반영했는지, 아니면 AI 쪽에서 직접 만들어야 하는지 확인 필요
- 테스트 코드가 현재 0개 — 최소한 서비스 레이어(캐시 조회/저장) 단위 테스트는 필요해 보임
- Charter(F-ZPVXHT)는 이번 인수인계 범위에 넣지 않았음 — 아직 손 안 댄 상태 그대로

## 관련 링크

- 이슈 #2: https://github.com/team-5io/AI-Fighters/issues/2
- PR #3: https://github.com/team-5io/AI-Fighters/pull/3
- API 계약: [docs/api_contract.md](api_contract.md)
- ERD: [docs/erd_ai_domain.sql](erd_ai_domain.sql)
