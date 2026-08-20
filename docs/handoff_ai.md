# AI 파트 인수인계

담당: 김민섭 (AI)

## 버전 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.0.0 | 2026-08-10 | 최초 작성 — Translation 캐시 레이어 작업(#2, #3) 기준 |
| v2.0.0 | 2026-08-21 | Writing Assistant 영어 출력 버그 수정(#24) 및 다국어(locale) 대응 설계(#26) 반영. 전면 재작성 |

> v1.0.0 본문은 현재 상태와 어긋나는 내용(테스트 0개, `google-genai==2.17.0` 등)이 있어
> v2.0.0에서 대체했다. 원문이 필요하면 git 히스토리에서 확인할 것.

---

# 1. 현재 상태 요약 (2026-08-21)

| 항목 | 상태 |
|---|---|
| 테스트 | **56 passed** (`.venv/bin/python -m pytest -q`) |
| LLM | `gemini-flash-lite-latest`, `google-genai==1.47.0` |
| 배포 | main push 시 CI가 자동으로 build → EC2 deploy (`.github/workflows/ci.yml`) |
| PR #24 | **머지 완료** (main까지 반영) |
| PR #26 | **OPEN — 회의 결정 대기** |
| locale 구현 | **미착수.** 설계만 확정, 코드는 한 줄도 안 건드림 |

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

## 2.2 다국어(locale) 대응 설계 (PR #26, OPEN)

설계 문서: [`docs/superpowers/specs/2026-08-21-ai-output-locale-design.md`](superpowers/specs/2026-08-21-ai-output-locale-design.md)

**해결하려는 문제**: AI가 자연어를 생성하는 지점 세 곳이 **전부 한국어로 하드코딩**되어 있다.
PR #24는 "한국어 고정"이었고, 이 설계는 그 고정을 사용자 언어 기반으로 일반화한다.

| 지점 | 파일 | 현재 |
|---|---|---|
| Writing Assistant 제안 | `services/writing_assistant.py` | `"...must be written in Korean."` |
| Charter 규칙 초안 | `services/charter.py` | `"...written in Korean."` |
| DocumentLion 이슈 설명 | `services/document_lion.py` | 프롬프트 전문이 한국어 |

---

# 3. 확정된 설계 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | locale 출처는 BE `UserEntity.language` | 이미 존재. BE 스키마 추가 불필요 |
| D2 | 적용 범위는 AI 생성 텍스트 **전체** (3곳) | 일부만 하면 외국 사용자에게 반쪽으로 보임 |
| D3 | 화이트리스트 + 폴백. **422를 내지 않는다** | BE의 502 래핑 함정 회피 (5.2 참고) |
| D4 | 미지원 locale의 폴백은 **영어** | 한국어보다 범용적 |
| D5 | 저장된 텍스트는 **조회 시 번역** | 다국어 팀에서 기존 규칙도 읽혀야 함 |
| D6 | 번역은 **최초 조회 시 lazy + 캐시** | 아무도 안 읽는 언어에 쿼터를 쓰지 않음 |
| D7 | 여러 건은 **1회 LLM 호출로 배치** | 지연·쿼터 절감 |
| D8 | 번역 실패 시 **원문 노출** | 기존 Translation 정책과 동일 |

## 3.1 계약 변경 (구현 시 반영할 것)

**생성 계열 — 요청 바디에 `locale` (optional)**

```
POST /api/ai/writing-assistant/suggestions
POST /api/ai/document-lion/reviews
POST /api/ai/charter/generate
PATCH /api/ai/charter/rules/{ruleId}
```

**조회 계열 — 쿼리 파라미터 `locale`**

```
GET /api/ai/charter/rules?teamId=1&locale=ja
GET /api/ai/document-lion/reviews/{reviewId}?locale=ja
```

## 3.2 폴백 규칙

| 입력 | 결과 |
|---|---|
| 누락 / `null` / 공백 | `ko` (하위 호환) |
| `ko` / `en` / `ja` | 그대로 |
| `KO`, `ko-KR`, `ko_KR` | `ko` (대소문자·지역 서브태그 정리) |
| `th`, `Korean` 등 | `en` + 경고 로그 |

## 3.3 신규 파일·테이블

- `app/core/locale.py` (신규) — `normalize_locale()`, `language_instruction()`, `language_name()`
- `ai_text_translation` 테이블 (신규) — `UNIQUE(entity_type, entity_id, field, target_locale)`
- `charter_rule.source_locale`, `document_review.source_locale` 컬럼 추가

---

# 4. 확인된 BE(Spring) 사실

BE 레포: `/Users/mnppi223/Desktop/dev/BACK-Fighters`

`UserEntity.language`는 `String`이고 Swagger 예시가 `"ko"`다.
**BCP-47 코드 규약이 맞으므로 BE 쪽 코드 매핑은 불필요하다.**

다만 세 가지 제약이 있다.

| 발견 | 위치 | 영향 |
|---|---|---|
| `@Column private String language` — **nullable** | `UserEntity.java:41` | 값이 없는 사용자가 존재 |
| 가입 시 `language`를 채우지 않음 | `SignupService.java:38` | **신규 가입자가 전부 `null`** |
| `language`에 검증 없음 (`@NotBlank`·`@Pattern`·enum 전부 없음) | `UpdateProfileRequest.java:15` | `"KO"`, `"ko-KR"` 등 유입 가능 |

1·3번은 설계의 폴백 규칙(3.2)이 흡수한다. **2번은 제품 결정이 필요하다** (6절 참고).

**BE 작업 범위**

1. `UserEntity.language`를 AI 프록시 호출에 실어 보낸다 (POST 4곳, GET 2곳)
2. 값이 `null`이면 필드를 생략하거나 `null`로 보내면 된다 — AI가 기본값 처리
3. `docs/api_contract.md` 갱신
4. (선택) `UpdateProfileRequest.language`에 `@Pattern` 검증 추가

---

# 5. 반드시 알아야 할 함정

## 5.1 Alembic이 없다 — 컬럼 추가는 자동으로 안 된다

`scripts/create_tables.py`는 `Base.metadata.create_all`을 호출한다.
이것은 **없는 테이블만 생성하고, 기존 테이블에 컬럼을 추가하지 않는다.**

- `ai_text_translation` 신규 테이블 → `create_all`로 생성됨. 모델만 추가하면 됨
- `source_locale` 컬럼 2개 → **`create_all`로 안 생긴다.** 별도 DDL 필요

```sql
ALTER TABLE charter_rule    ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
ALTER TABLE document_review ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
```

기본값 `'ko'`로 기존 행이 정확히 백필된다 (지금까지 생성된 텍스트는 전부 한국어).
**배포 시 이 SQL 실행을 빠뜨리면 조회에서 터진다.**

## 5.2 AI의 422는 BE에서 502로 보인다

AI가 `422`를 내면 BE가 `502`로 감싸서 내려보내고, 화면에는 "AI 장애"로 보인다.
실제로는 BE 요청 버그다. 이 프로젝트에서 이미 겪은 유형이다.

**그래서 `locale`을 required가 아니라 optional로 잡았다.** AI를 먼저 배포하고 BE가 나중에
붙는 롤아웃 순서에서, required면 그 사이 모든 호출이 422가 된다.

> 디버깅 팁: BE에서 502가 보이면 `Caused by`를 먼저 확인할 것. 422면 AI 코드가 아니라
> BE 요청을 봐야 한다.

## 5.3 git 브랜치는 반드시 `--no-track`

```bash
git checkout -b <새이름> origin/develop --no-track
```

`--no-track` 없이 만들면 새 브랜치의 업스트림이 `origin/develop`으로 잡혀서,
push할 때 새 브랜치가 아니라 develop에 직접 커밋이 꽂힐 수 있다.
push 전에 항상 `git branch -vv`로 확인할 것.

## 5.4 기존 테스트 하나가 수정 대상

`tests/test_writing_assistant_llm.py::test_prompt_requires_korean_output`

현재는 "항상 한국어"를 검증한다. locale 구현 이후 의미가 **"기본값이 한국어"** 로 바뀌므로
같이 고쳐야 한다.

---

# 6. 회의에서 정해야 할 것 (딱 하나)

**신규 가입자의 기본 언어.**

현재 `SignupService`가 `language`를 채우지 않아 신규 가입자는 전부 `null`이고,
설계상 `null`은 한국어로 처리된다. 즉 **일본에서 막 가입한 사용자도 프로필을 직접
바꾸기 전까지는 한국어를 받는다.**

| 안 | 내용 | 평가 |
|---|---|---|
| (a) | 현행 유지 — `null`이면 한국어 | 가장 단순. 외국 신규 가입자가 한국어를 봄 |
| (b) | 가입 시 `Accept-Language`로 초기값, 해석 불가 시 영어 | **권장** |
| (c) | 온보딩에서 언어를 직접 묻는다 | 가장 정확하나 온보딩 단계가 늘어남 |

이 결정이 나와야 PR #26을 머지하고 구현으로 넘어간다.

---

# 7. 검토했으나 채택하지 않은 대안

동일한 논의가 반복되지 않도록 기록해둔다. 상세는 설계 문서 11절 참고.

## 7.1 FE 브라우저 온디바이스 번역 (Translator API)

조회 시 번역을 FE 브라우저 내장 API로 처리하는 안. 채택하면 설계 6·7절이 통째로
불필요해지고 API 쿼터도 안 든다. **2026-08-21 조사 결과 주 경로로는 채택하지 않는다.**

| 항목 | 확인된 사실 |
|---|---|
| 지원 브라우저 | Chrome 138+ / Edge 148+ |
| Firefox · Safari | 미지원 |
| 모바일 | 전 플랫폼 미지원 |
| 용어 보존(glossary) | 기능 없음 |
| 실행 조건 | user activation 필요 — 로드 시 자동 번역 불가 |
| 기타 | Web Worker 불가, 순차 처리, 최초 사용 시 모델 다운로드 |

**제외 사유**

1. Safari와 모든 모바일에서 동작하지 않아 해결 대상 시나리오의 절반 이상을 놓친다
2. 용어 보존이 없어 `"Doc PR"`, `"RACI"`가 번역된다 — `preservedTerms`를 갖춘 기존
   "Dev-aware Translation" 설계와 정면 충돌한다
3. 서버 번역 비용이 실제로는 낮다. 배치 + 캐시로 **"팀 × 대상 언어" 조합당 사실상 1회**이며,
   규칙이 수정되지 않는 한 재호출이 없다

**재검토 조건**: Safari·모바일 지원 + glossary 기능이 추가되면 다시 볼 가치가 있다.
그때는 서버 번역을 유지한 채 지원 브라우저에서만 쓰는 점진적 향상으로 붙일 수 있다.

## 7.2 신규 가입자 기본값을 영어로 고정

한국어 사용자가 프로필 수정 전까지 영어 제안을 받게 되는데, 이는 PR #24로 수정한
버그와 **사용자 입장에서 동일한 증상**이다. 버그로 고친 동작을 설계로 되살리는 셈이라
제외했다. 대신 (b) `Accept-Language` 안을 권장한다.

---

# 8. 다음 작업 순서

1. **회의에서 (a)/(b)/(c) 결정** ← 현재 여기서 막혀 있음
2. 결정을 설계 문서에 반영하고 **PR #26 머지**
3. 구현 계획 작성 (`docs/superpowers/plans/`)
4. 구현 — 롤아웃 순서대로
   1. `app/core/locale.py` + 서비스 3곳의 생성 시점 locale 적용 (`locale` optional)
      → 이 시점에 배포해도 BE 변경 없이 현행 동작이 유지된다
   2. 마이그레이션 SQL 적용 + `ai_text_translation` 모델 추가
   3. 조회 시 번역 구현
   4. BE가 locale 전달 시작
   5. `api_contract.md` 갱신

1번과 4번 사이에는 언제든 배포 가능한 상태가 유지된다.

---

# 9. 남아 있는 이전 과제

v1.0.0에서 넘어온 것 중 아직 유효한 항목.

- **DocumentLion `conflict`/`inconsistency` 미구현** — BE의 `GET /documents/{id}/graph`가
  아직 없어 항상 이슈 없음으로 나온다. API 준비되면 연동
- **DocumentLion `locationRef` 포맷 미확정** — FE 에디터의 문장/섹션 식별 방식에 맞춰야 함
- **Writing Assistant 제안 유형별 그룹핑 여부 미확정** — API 응답 필드는 양쪽 다 가능하게 잡혀 있음
- **DocumentLion에 Flash-Lite로 충분한지** — 추론 난이도가 높아 상위 모델 필요 여부 논의 필요

---

# 10. 링크

- 설계 문서: [`docs/superpowers/specs/2026-08-21-ai-output-locale-design.md`](superpowers/specs/2026-08-21-ai-output-locale-design.md)
- PR #24 (머지됨): https://github.com/team-5io/AI-Fighters/pull/24
- PR #26 (OPEN): https://github.com/team-5io/AI-Fighters/pull/26
- API 계약: [docs/api_contract.md](api_contract.md)
- 배포: [docs/deploy.md](deploy.md)
- ERD: [docs/erd_ai_domain.sql](erd_ai_domain.sql)
- BE 레포: https://github.com/team-5io/BACK-Fighters
