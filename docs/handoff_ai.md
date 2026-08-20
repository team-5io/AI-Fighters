# AI 파트 인수인계

담당: 김민섭 (AI)

## 버전 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.0.0 | 2026-08-10 | 최초 작성 — Translation 캐시 레이어 작업(#2, #3) 기준 |
| v2.0.0 | 2026-08-21 | Writing Assistant 영어 출력 버그 수정(#24) 및 다국어(locale) 대응 설계(#26) 반영. 전면 재작성 |
| v2.1.0 | 2026-08-21 | 미결정 6건 확정 및 **AI 구현 완료** 반영. 6절이 "정할 것"에서 "결정 완료"로 바뀜 |
| v3.0.0 | 2026-08-21 | **방향 전환.** AI는 항상 영어 생성, 번역은 FE 온디바이스. locale 구현 전부 제거 |

> v1.0.0 본문은 현재 상태와 어긋나는 내용(테스트 0개, `google-genai==2.17.0` 등)이 있어
> v2.0.0에서 대체했다. 원문이 필요하면 git 히스토리에서 확인할 것.

---

# 0. 방향 전환 (2026-08-21) — 먼저 읽을 것

**AI는 항상 영어로 생성한다. 사용자 언어로의 번역은 FE 브라우저 온디바이스 번역이 담당한다.**

v2.x에서 구현했던 locale 기반 설계는 **전부 제거했다.** 서버에는 이제 언어 개념이 없다.

| 제거된 것 | |
|---|---|
| `app/core/locale.py` | 삭제 |
| 요청 스키마의 `locale` 필드 4곳 | 삭제 |
| `source_locale` 컬럼 2개 | 모델에서 삭제 |
| `ai_text_translation` 테이블·모델 | 삭제 |
| 배치 번역(`call_batch_translation_llm`, 청크 분할) | 삭제 |
| 조회 시 번역 (`app/services/ai_text_translation.py`) | 삭제 |
| GET 두 곳의 `locale` 쿼리 파라미터 | 삭제 |
| `2026-08-21_add_source_locale.sql` | 삭제 |

| 남은 것 (locale과 무관) | |
|---|---|
| `blocks` + `locationRef` 객체 | 유효 |
| `relatedDocuments` (conflict/inconsistency) | 유효 |
| 제안 정렬 (`structure`→`next-paragraph`→`clarity`) | 유효 |
| `document_lion_model` / `cio_model` 설정 분리 | 유효 |
| 마이그레이션 자동화 + `/health` 스키마 검증 | 유효 |

**출력 언어 지시는 `app/core/output_language.py` 상수 하나로 관리한다.** PR #24가 정확히
이 지시가 빠져서 난 버그다. 세 서비스가 각자 문장을 적으면 한 곳이 빠진다.

## 0.1 프로덕션 DB에 `source_locale`이 이미 있으면

**남겨둬도 무해하다.** `NOT NULL DEFAULT 'ko'`이므로 컬럼을 명시하지 않는 INSERT도 통과한다.
굳이 `DROP`하지 않는다 — 파괴적이고 얻는 것이 없다.

## 0.2 온디바이스 번역의 알려진 제약 (다시 조사하지 말 것)

2026-08-21에 조사해 설계 문서 11.1절에 기록해뒀다. **팀은 이 제약을 알고 온디바이스를 택했다.**

| 항목 | 확인된 사실 |
|---|---|
| 지원 브라우저 | Chrome 138+ / Edge 148+ |
| Firefox · Safari | 미지원 |
| 모바일 | 전 플랫폼 미지원 |
| 용어 보존(glossary) | 기능 없음 — `Doc PR`, `RACI`가 번역된다 |
| 실행 조건 | user activation 필요 — 로드 시 자동 번역 불가 |

**FE가 감안해야 할 것**: 미지원 브라우저에서는 영어가 그대로 노출된다. 그리고
`locationRef.quote`는 **번역 대상에서 제외해야 한다** — 번역하면 원문에서 그 문장을 못 찾는다.

---

# 1. 현재 상태 요약 (2026-08-21)

| 항목 | 상태 |
|---|---|
| 테스트 | **116 passed** (`.venv/bin/python -m pytest -q`) — locale 테스트 제거로 207 → 116 |
| LLM | `gemini-flash-lite-latest`, `google-genai==1.47.0` |
| 배포 | main push 시 CI가 자동으로 build → EC2 deploy (`.github/workflows/ci.yml`) |
| 미결정 사항 | 없음 — 방향 전환으로 locale 논의 자체가 종료 |
| AI 구현 | **완료.** locale 제거까지 반영 |
| BE 작업 | **미착수** — 2건 (5.1절) |
| FE 작업 | **미착수** — 5건 (5.2절) |
| 실제 API 호출 | 구현 중 0회 — 전부 mock |

## 1.1 PR 이력

| PR | 상태 | 내용 |
|---|---|---|
| #24 | 머지 | Writing Assistant 영어 출력 버그 수정 |
| #26 | 머지 | locale 설계 문서 + 인수인계서 v2.0.0 → **설계는 폐기됨** |
| #27 | 머지 | locale 구현 → **이번에 되돌림** |
| #28 | 머지 | develop → main 릴리스 |
| #29 | 머지 | `relatedDocuments`, `/graph` 오기 정정 |
| #30 | 머지 | 마이그레이션 자동화 + `/health` 스키마 검증 |

`locale` 제거 PR이 이 문서와 함께 올라간다.

**되돌린 것을 git에서 지우지 않았다.** revert 대신 새 커밋으로 제거했다. 필요하면
`#27`의 diff에서 원래 구현을 볼 수 있다.
---

# 2. 이번 세션에서 한 일

## 2.1 Writing Assistant 영어 출력 버그 수정 (PR #24, 머지됨)

**증상**: 글쓰기 제안이 화면에 영어로 노출됨.

**초기 오진**: UTF-8 인코딩 문제로 의심했으나 **아니었다.**

- 응답이 mojibake(`ë¬¸ìì`)가 아니라 정상적인 영어 문장이었다
- 같은 화면의 다른 한글 UI("문서 작성을 도와드릴까요?", "수락")는 정상 렌더링됐다
- 라우트·스키마에 인코딩을 조작하는 코드가 없고, FastAPI `JSONResponse`는 기본이 UTF-8이다

**실제 원인**: `app/services/writing_assistant.py`의 프롬프트가 영어로 작성되어 있고
**출력 언어를 지정하는 문장이 없었다.** Gemini는 지시가 없으면 프롬프트 언어를 따라간다.

같은 레포의 다른 서비스와 비교하면 명확하다.

| 파일 | 프롬프트 | 출력 |
|---|---|---|
| `services/charter.py` | 영어 + `"written in Korean."` 명시 | 한국어 정상 |
| `services/document_lion.py` | 프롬프트 전문이 한국어 | 한국어 정상 |
| `services/writing_assistant.py` | 영어, 언어 지시 없음 | **영어** |

**수정 내용**

- `app/services/writing_assistant.py` — 프롬프트에 `"Every suggestion text must be written in Korean."` 추가
- `tests/test_writing_assistant_llm.py` — 회귀 방지 테스트 `test_prompt_requires_korean_output` 추가

**검증**

- 전체 테스트 56 passed
- 실제 Gemini 호출 1회로 한국어 출력 확인 (아래는 실제 응답)

```
1. [structure] 외국어의 인사말 사례를 비교하는 섹션을 추가하여 문화적 다양성을 다루어보세요.
2. [next-paragraph] 이어서 이러한 축약형 인사말이 세대 간 소통에 미치는 영향과 변화 양상에 대해 작성해 보세요.
3. [clarity] '온라인에서는'이라는 표현을 '디지털 소통 환경에서는'과 같이 더 구체적인 학술적 용어로 다듬어 명확성을 높이세요.
```

> 실호출 시 google-genai SDK가 `thought_signature` 관련 경고를 출력한다. **무해하다.**
> 모델의 thinking part를 만나면 나오는 경고이며 `response.parsed`는 정상적으로 채워진다.

## 2.2 다국어 대응 — 설계 후 방향 전환

`locale` 기반 설계를 구현해 배포까지 했다가(PR #26·#27·#28), **팀 결정으로 전부 되돌렸다.**
AI는 항상 영어로 생성하고 번역은 FE 온디바이스가 담당한다. 상세는 **0절**.

되돌리는 과정에서 부수적으로 얻은 것이 세 개 있고, 이건 locale과 무관해서 그대로 남았다 —
`blocks`/`locationRef`, `relatedDocuments`, 마이그레이션 자동화.

---

# 3. 유효한 설계 결정

locale 관련 결정(D1~D9, D13)은 0절대로 전부 폐기됐다. 남은 것은 아래 셋이다.

| # | 결정 | 근거 |
|---|---|---|
| D10 | `locationRef`는 `{"blockId","quote"}` 객체 | 제품이 이미 블록 단위(Translation이 `blockId`를 씀) |
| D11 | 제안은 평평한 리스트 + 서버 정렬 | 계약 변경 없이 순서 불안정만 해결 |
| D12 | DocumentLion·CIO 모델 설정 분리, 값은 유지 | 측정 전에 값을 바꾸지 않음 |

추가로 이번에 정한 것.

| 결정 | 근거 |
|---|---|
| `relatedDocuments`로 conflict/inconsistency 검토 | BE `/relations`에 본문이 없어 BE가 실어 보내야 함 |
| 마이그레이션은 배포가 자동 적용 | 사람이 EC2에 붙는 단계 제거 |
| `/health`가 DB 스키마까지 검증 | 상수 응답이면 배포가 조용히 성공으로 찍힘 |

## 3.1 현재 계약

**요청에 언어 필드가 없다.** 아래가 전부다.

```
POST /api/ai/writing-assistant/suggestions   documentId, content, cursorContext
POST /api/ai/document-lion/reviews           ... + blocks?, relatedDocuments?
POST /api/ai/charter/generate                teamId
PATCH /api/ai/charter/rules/{ruleId}         title, description
GET  /api/ai/charter/rules?teamId=1
GET  /api/ai/document-lion/reviews/{reviewId}
```

`blocks`와 `relatedDocuments`는 optional이다. 이유는 5.2절.

---

# 4. 반드시 알아야 할 함정

## 4.1 출력 언어 지시는 상수 하나로 관리한다

`app/core/output_language.py`의 `OUTPUT_LANGUAGE_INSTRUCTION`이 유일한 출처다.

**PR #24가 정확히 이 지시가 빠져서 난 버그다.** 프롬프트에 출력 언어 지시가 없으면 Gemini가
프롬프트 언어를 따라간다. 세 서비스가 각자 문장을 적으면 한 곳이 빠지거나 표현이 갈라진다.

`document_lion.py`는 프롬프트 본문이 한국어다. **지시가 빠지면 한국어로 새어나간다.**
프롬프트를 영어로 재작성하는 것은 검토 품질을 바꿀 수 있어 범위 밖이다(설계 12절).

## 4.2 AI의 422는 BE에서 502로 보인다

AI가 `422`를 내면 BE가 `502`로 감싸 내려보내 화면에는 "AI 장애"로 보인다. 실제로는 BE 요청
버그다. **그래서 `blocks`·`relatedDocuments`를 required가 아니라 optional로 잡았다.**

> 디버깅 팁: BE에서 502가 보이면 `Caused by`를 먼저 볼 것. 422면 AI 코드가 아니라 BE 요청이다.

## 4.3 Alembic이 없다 — 다만 이제 자동이다

`create_all`은 없는 테이블만 만들고 기존 테이블에 컬럼을 추가하지 않는다. 그 간극을
`scripts/run_migrations.py`가 메운다. **배포가 자동으로 적용한다.**

`scripts/migrations/`에 SQL 파일을 추가해 머지하면 끝이다. EC2 접속 불필요. 상세는
`scripts/migrations/README.md`와 `docs/deploy.md`.

## 4.4 `/health`는 DB를 요구한다

`deploy` job은 `curl -sf /health` 하나로 성공을 판정한다. 이제 앱이 읽는 테이블을 실제로
조회하므로, **DB가 내려가 있거나 스키마가 어긋나면 배포가 실패로 판정된다.** 의도된 동작이다.

`SELECT 1`로는 컬럼 누락이 잡히지 않아 모델 조회로 검증한다.

## 4.5 git 브랜치는 반드시 `--no-track`

```bash
git checkout -b <새이름> origin/develop --no-track
```

없이 만들면 업스트림이 `origin/develop`으로 잡혀 push가 develop에 직접 꽂힐 수 있다.
push 전에 항상 `git branch -vv`로 확인할 것.

## 4.6 LLM은 존재하지 않는 식별자를 만들어낸다

`blockId`와 `relatedDocuments`의 `documentId` 둘 다 **전달한 집합에 없으면 버린다.**
검증 없이 저장하면 FE가 없는 블록·문서를 찾다 조용히 실패한다.

---

# 5. BE·FE 작업 지시

## 5.1 BE

**언어 관련 작업은 전부 없어졌다.** `locale` 전달, `Accept-Language` 초기값,
`Language` enum 전환 — v2.1.0에 적어뒀던 세 건 모두 **폐기**다. AI는 사용자 언어를 받지 않는다.

남은 것은 둘이다.

**(1) DocumentLion 호출에 `blocks`를 실어 보낸다** (optional)

```json
"blocks": [{ "blockId": "string", "content": "string" }]
```

Translation 호출에서 이미 보내는 `blockId`와 같은 값이다. 보내면 이슈 위치를 FE가 정확히
하이라이트할 수 있다. 생략하면 `content` 평문으로 검토하고 `locationRef.blockId`가 `null`이 된다.

**(2) DocumentLion 호출에 `relatedDocuments`를 실어 보낸다** (optional)

```json
"relatedDocuments": [
  { "documentId": 200, "title": "...", "content": "...", "relationType": "REFERENCE", "direction": "OUTGOING" }
]
```

두 단계다.

1. `GET /documents/{documentId}/relations`로 이웃 문서를 찾는다
2. **이웃 문서 본문까지 조회해서** 위 형태로 실어 보낸다

2단계가 필요한 이유: `/relations` 응답에 본문이 없다 — `relationId`, `direction`,
`relationType`, `neighborDocumentId`, `neighborTitle`, `createdAt`뿐이다.

> **`/graph`가 아니라 `/relations`다.** BE 인수인계서(`handoff_be_ai_integration.md`)에
> "Document Graph API가 없다"고 적혀 있는데, 실제 API는 `/relations` 이름으로 BE `72efa68`
> (2026-08-17)에 이미 들어가 있다. 없는 이름을 찾고 있어서 `conflict`/`inconsistency`가
> 실재하지 않는 블로커로 오래 막혀 있었다. **BE 인수인계서도 고쳐야 한다.**

생략하면 `charter_violation`만 검사하는 기존 동작이 유지된다.

## 5.2 FE

**AI가 내려주는 모든 자연어는 영어다.** 사용자 언어 번역은 FE 온디바이스가 담당한다.

**(1) `locationRef.quote`는 번역 대상에서 제외할 것.**
원문 문서에서 그대로 발췌한 문장이다. 번역하면 문서에서 그 문장을 찾을 수 없다.
`description`은 영어이므로 번역 대상이다.

**(2) `locationRef`가 문자열 → 객체다.**
`{"blockId": string|null, "quote": string|null}`. 포맷 확정 전에 저장된 행은
`{"blockId": null, "quote": "<원래 문자열>"}`로 내려와 깨지지 않는다.

**(3) 제안 순서가 고정됐다.**
`structure` → `next-paragraph` → `clarity`. 필드는 그대로라 수정은 없다.

**(4) 미지원 브라우저에서는 영어가 그대로 노출된다.**
Safari와 모든 모바일이 Translator API를 지원하지 않는다(0.2절). 폴백 UX를 정해야 한다.

**(5) `Doc PR`, `RACI` 같은 도메인 용어가 번역된다.**
온디바이스 API에 glossary 기능이 없다. Translation 엔드포인트의 `preservedTerms`와
동작이 어긋나는 지점이라 FE에서 어떻게 다룰지 정해야 한다.

**확인 부탁할 것 하나**: 에디터가 블록 기반인가. `locationRef`를 `blockId` 기준으로 잡았다.
계약상 `blockId`를 FE가 생성한다고 되어 있어 블록 기반으로 추정했으나 FE 코드를 직접 본 것은 아니다.

---

# 6. 다음 작업 순서

1. **이 방향 전환 PR 리뷰·머지** ← 현재 여기
2. `main` 릴리스 → 배포. **마이그레이션은 이제 자동이다**
3. BE 작업 2건 (5.1절)
4. FE 작업·확인 (5.2절) — 특히 (4)(5) 폴백 정책
5. DocumentLion 모델 품질 측정 — 별도 승인 후 (설계 14.3절)

---

# 7. 남아 있는 과제

- **Writing Assistant 제안 개수 제한 미확정** — 현재 기본 3개(`writing_assistant_suggestion_count`)
- **번역 실패 시 재시도 버튼 여부 미확정** — 현재는 즉시 원문 표시
- **온디바이스 미지원 브라우저 폴백 UX 미정** (5.2절 (4))
- **도메인 용어 보존 정책 미정** (5.2절 (5)) — `preservedTerms` 설계와 충돌
- **DocumentLion에 Flash-Lite로 충분한지 미측정** — 설정은 분리해뒀다(D12)
- **`document_lion.py` 프롬프트 영어 재작성** — 검토 품질에 영향, 별도 과제
- **Alembic 도입** — 자동화로 급하지 않아졌다. 스키마 변경이 잦아지면 재검토

---

# 8. 링크

- 설계 문서(**폐기**): [`docs/superpowers/specs/2026-08-21-ai-output-locale-design.md`](superpowers/specs/2026-08-21-ai-output-locale-design.md)
  — 상단 경고 참고. 유효한 것은 14.1~14.3절뿐. **11.1절의 온디바이스 조사 결과는 지금도 유효하다**
- PR 이력: 1.1절
- 출력 언어 지시 상수: `app/core/output_language.py`
- 마이그레이션: `scripts/migrations/README.md` — 배포가 자동 적용한다
- API 계약: [docs/api_contract.md](api_contract.md)
- 배포: [docs/deploy.md](deploy.md)
- ERD: [docs/erd_ai_domain.sql](erd_ai_domain.sql)
- BE 레포: https://github.com/team-5io/BACK-Fighters
