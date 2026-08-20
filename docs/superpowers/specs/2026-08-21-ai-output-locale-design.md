# AI 생성 텍스트 다국어(locale) 대응 설계

- 작성일: 2026-08-21
- 상태: **설계 확정 + AI 구현 완료** (BE·FE 작업 대기)
- 영향 범위: AI-Fighters(FastAPI) + BE(Spring) — 두 레포에 걸침

---

## 1. 배경

서비스를 여러 나라 사용자가 쓰게 되면서, AI가 생성하는 자연어 출력이 사용자의 언어로 나와야 한다.
일본 사용자는 일본어로, 미국 사용자는 영어로 받아야 한다.

현재 AI가 자연어를 생성하는 지점은 세 곳이며, **세 곳 모두 한국어가 하드코딩되어 있다.**

| 지점 | 위치 | 현재 상태 |
|---|---|---|
| Writing Assistant 제안 | `app/services/writing_assistant.py` | 프롬프트에 `"...must be written in Korean."` |
| Charter 규칙 초안 | `app/services/charter.py` | 프롬프트에 `"...written in Korean."` |
| DocumentLion 이슈 설명 | `app/services/document_lion.py` | 프롬프트 전문이 한국어 |

> 참고: 2026-08-21에 Writing Assistant의 한국어 출력 지시가 누락되어 영어로 응답하던 버그를 수정했다
> (PR #24). 그 수정은 "한국어 고정"이었고, 본 설계는 그 고정을 locale 기반으로 일반화한다.

### 인코딩 문제가 아니다

초기에 UTF-8 인코딩 문제로 의심했으나 아니다. 응답이 mojibake가 아닌 정상 영어 문장이었고,
FastAPI `JSONResponse`는 기본이 UTF-8이며 라우트/스키마에 인코딩을 조작하는 코드가 없다.
순수하게 **프롬프트의 출력 언어 지시** 문제다.

---

## 2. 확정된 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | locale 출처는 **BE 사용자 프로필의 선호 언어** | 이미 존재하는 필드. BE 스키마 추가 불필요 |
| D2 | 적용 범위는 **AI 생성 텍스트 전체** (3개 지점) | 일부만 하면 일본 사용자에게 반쪽으로 보임 |
| D3 | 지원 언어는 **화이트리스트 + 폴백** (422 거부 안 함) | AI의 422를 BE가 502로 감싸는 기존 함정 회피 |
| D4 | 미지원 locale의 폴백은 **영어** | 한국어보다 범용적 |
| D5 | 저장된 텍스트는 **조회 시 번역**한다 (B안) | 다국어 팀에서 기존 규칙/검토결과도 읽혀야 함 |
| D6 | 번역은 **최초 조회 시점에 lazy 수행 + 캐시** | 아무도 읽지 않는 언어에 API 쿼터를 쓰지 않음 |
| D7 | 여러 건 번역은 **1회 LLM 호출로 배치** | 지연·쿼터 모두 절감 |
| D8 | 번역 실패 시 **원문 그대로 노출** | 기존 Translation 정책(`실패 즉시 원문 표시`)과 동일 |
| D9 | 신규 가입자 기본 언어는 **`Accept-Language`, 실패 시 영어** | 온보딩 단계를 늘리지 않고 자동 분기. 13절 참고 |
| D10 | `locationRef`는 **`{"blockId","quote"}` 객체** | 제품이 이미 블록 단위. 14.1절 참고 |
| D11 | 제안은 **평평한 리스트 + 서버 정렬** | 계약 변경 없이 순서 불안정 문제만 해결. 14.2절 참고 |
| D12 | DocumentLion·CIO **모델 설정만 분리, 값은 유지** | 측정 전에 값을 바꾸지 않는다. 14.3절 참고 |
| D13 | 배치 번역 청크는 **문자 수 4,000자 기준** | 개수로는 항목 길이 편차를 못 잡는다. 14.4절 참고 |

---

## 3. locale 전달 계약

AI-Fighters에는 인증도 BE DB 접근도 없다(`docs/api_contract.md`). 따라서 locale은
**BE가 프록시 호출 시 명시적으로 전달**해야 한다. 다른 경로는 없다.

### 3.1 값 포맷

BCP-47 소문자 코드: `"ko"`, `"en"`, `"ja"`.
Translation 엔드포인트가 이미 `sourceLang: "ko"` / `targetLang: "en"`을 쓰고 있어 그와 통일한다.

**(2026-08-21 확인 완료)** BE `UserEntity.language`는 `String`이고 Swagger 예시가 `"ko"`다.
BCP-47 코드 규약이 맞으므로 **BE 쪽 코드 매핑은 불필요하다.**

다만 확인 과정에서 세 가지 제약이 드러났다.

| 발견 | 영향 |
|---|---|
| `@Column private String language` — **nullable** | 값이 없는 사용자가 존재한다 |
| `SignupService`가 가입 시 `language`를 채우지 않는다 | **모든 신규 가입자가 `null`로 시작**한다 |
| `UpdateProfileRequest.language`에 검증이 없다 (`@NotBlank`·`@Pattern`·enum 전부 없음) | `"KO"`, `"ko-KR"`, `"Korean"` 등 임의 문자열이 저장될 수 있다 |

1번과 3번은 본 설계의 폴백 규칙(3.4)이 이미 흡수한다.
2번은 제품 결정이 필요하며 13절 열린 질문으로 남긴다.

### 3.2 필드 위치

**생성 계열(POST/PATCH) — 요청 바디**

```json
POST /api/ai/writing-assistant/suggestions   { ..., "locale": "ja" }
POST /api/ai/document-lion/reviews           { ..., "locale": "ja" }
POST /api/ai/charter/generate                { "teamId": 1, "locale": "ja" }
PATCH /api/ai/charter/rules/{ruleId}         { ..., "locale": "ja" }
```

**조회 계열(GET) — 쿼리 파라미터**

```
GET /api/ai/charter/rules?teamId=1&locale=ja
GET /api/ai/document-lion/reviews/{reviewId}?locale=ja
```

### 3.3 optional로 두는 이유

`locale`은 **필수가 아니다.** 누락 시 기본값 `ko`로 동작한다.

AI를 먼저 배포하고 BE가 나중에 붙는 롤아웃 순서에서, required로 잡으면 그 사이 모든 호출이
`422`가 되고 BE가 이를 `502`로 감싸 내려보내 화면에는 "AI 장애"로 보인다. 이 프로젝트에서
이미 겪은 유형의 사고다. optional이면 BE 미배포 구간에도 현행 동작이 그대로 유지된다.

### 3.4 폴백 규칙

| 입력 | 결과 | 이유 |
|---|---|---|
| 누락 / `null` / 공백 | `ko` | 하위 호환 — BE 미배포 구간의 현행 동작 유지 |
| 지원 목록 내 (`ko`/`en`/`ja`) | 그대로 | — |
| 대소문자·지역코드 변형 (`KO`, `ko-KR`, `ko_KR`) | `ko` | BE에 검증이 없어 실제로 유입 가능 (3.1) |
| 지원 목록 밖 (`th`, `Korean` 등) | `en` + 경고 로그 | 한국어보다 범용적 (D4) |

---

## 4. 공용 locale 모듈 — `app/core/locale.py` (신규)

세 서비스가 각자 언어 지시 문자열을 조립하면 세 벌로 갈라진다. 단일 지점으로 묶는다.

```python
SUPPORTED_LOCALES = frozenset({"ko", "en", "ja"})
DEFAULT_LOCALE = "ko"      # locale 미전달 시
FALLBACK_LOCALE = "en"     # 지원하지 않는 값이 왔을 때

_LANGUAGE_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese"}

def normalize_locale(raw: str | None) -> str:
    """요청에서 받은 locale을 지원 언어로 정규화한다.

    BE가 값을 검증하지 않으므로(3.1) 다음 순서로 관대하게 처리한다.
      1. None/공백  -> DEFAULT_LOCALE
      2. 소문자화 후 지역 서브태그 제거 ("ko-KR", "ko_KR", "KO" -> "ko")
      3. SUPPORTED_LOCALES에 있으면 그대로, 없으면 FALLBACK_LOCALE + 경고 로그
    """

def language_instruction(locale: str) -> str:
    """프롬프트에 붙일 출력 언어 지시문을 만든다."""
    # -> "Write all natural-language output in Japanese."

def language_name(locale: str) -> str:
    """번역 프롬프트용 언어 이름."""
```

언어 이름을 영어로 쓰는 이유: 기존 프롬프트가 영어 기반이고, 영어 언어명이 모델에게 가장 모호하지 않다.

---

## 5. 생성 시점 언어 적용

### 5.1 서비스 3곳

| 파일 | 변경 |
|---|---|
| `services/writing_assistant.py` | 하드코딩된 한국어 지시문을 `language_instruction(locale)`로 교체 |
| `services/charter.py` | `"...written in Korean."`를 `language_instruction(locale)`로 교체 |
| `services/document_lion.py` | 한국어 지시문 본문은 유지하고, 출력 언어 지시 줄만 추가 |

`document_lion.py`의 프롬프트를 영어 기반으로 재작성하지 않는 이유: 그것은 검토 품질 자체를
바꿀 수 있는 변경이며 본 작업의 범위가 아니다. 출력 언어만 분리해 지시한다.
프롬프트 언어 통일은 별도 과제로 남긴다.

### 5.2 스키마 변경

`SuggestionRequest`, `ReviewRequest`, `GenerateCharterRequest`, `UpdateRuleRequest`에
`locale: str | None = None` 추가. `CamelModel`을 쓰므로 JSON 키도 `locale` 그대로다.

---

## 6. 저장된 텍스트의 조회 시 번역 (D5)

Writing Assistant는 응답 후 폐기되므로 5절로 끝난다.
**Charter 규칙과 DocumentLion 이슈는 DB에 저장**되므로 추가 설계가 필요하다.

### 6.1 문제

`charter_rule`과 `document_review_issue`는 생성 시점 언어로 저장된다.
한국인이 만든 규칙을 나중에 합류한 일본 사용자가 조회하면 한국어가 그대로 노출된다.
AI가 개입할 지점이 없다 — 이미 굳은 텍스트이기 때문이다.

또한 현재 두 테이블에는 **"어떤 언어로 저장되었는지" 기록이 없다.** 번역하려면 원본 언어를
알아야 하므로 칸부터 필요하다.

### 6.2 데이터 모델 변경

**(a) 기존 테이블에 원본 언어 칸 추가**

```sql
ALTER TABLE charter_rule
  ADD COLUMN source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';

ALTER TABLE document_review
  ADD COLUMN source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
```

- 기본값 `'ko'`로 기존 행이 정확히 백필된다 (현재까지 생성된 텍스트는 전부 한국어).
- `document_review_issue`가 아니라 부모인 `document_review`에 둔다. 한 리뷰의 이슈들은
  단일 LLM 호출로 한 번에 생성되므로 언어가 항상 동일하다. 칸을 하나만 두면 된다.
- **쓰기 시점에 채운다.** `create_draft_rules`와 `create_review`가 행을 만들 때
  `source_locale = normalize_locale(요청 locale)`을 함께 저장한다. 이 값이 비어 있으면
  이후 조회 시 원본 언어를 알 수 없어 번역 자체가 불가능하다.

**(b) 범용 번역 보관함 테이블 신규 — `ai_text_translation`**

```
id                UUID       PK
entity_type       VARCHAR(32)   -- 'charter_rule' | 'document_review_issue'
entity_id         UUID
field             VARCHAR(32)   -- 'title' | 'description'
target_locale     VARCHAR(10)
translated_text   TEXT
source_text_hash  VARCHAR(64)   -- 원본 텍스트의 sha256
created_at        TIMESTAMPTZ
updated_at        TIMESTAMPTZ

UNIQUE (entity_type, entity_id, field, target_locale)
```

기존 `translation_cache`를 재사용하지 않는 이유: 해당 테이블은
`document_ref BIGINT + block_ref VARCHAR + target_lang`으로 **문서 블록 전용**으로 설계되어
있다. 규칙·이슈는 문서도 블록도 아니므로, 억지로 끼워 넣으면 의미가 무너지고 유니크 제약이
충돌한다. 별도 테이블로 분리한다.

### 6.3 조회 흐름

`GET /api/ai/charter/rules?teamId=1&locale=ja` 기준:

```
1. DB에서 규칙 행을 조회한다
2. source_locale == 'ja' 인 행은 번역 불필요 — 원문 그대로 사용
3. 나머지 행의 (title, description)에 대해 ai_text_translation을 조회한다
   - 캐시 적중이면서 source_text_hash가 현재 원문 해시와 일치 → 그대로 사용
   - 없거나 해시 불일치 → 번역 대상으로 수집
4. 번역 대상이 있으면 source_locale별로 묶어 각 묶음당 LLM 1회 호출 (D7)
5. 결과를 ai_text_translation에 upsert
6. 번역문으로 치환해 응답
```

`GET /api/ai/document-lion/reviews/{reviewId}?locale=ja`도 동일하며,
대상 필드는 `document_review_issue.description` 하나다.
`location_ref`는 위치 참조값이므로 번역하지 않는다.
이슈의 원본 언어는 부모인 `document_review.source_locale`을 따른다 (6.2 참고).

**생성 계열 POST 응답은 번역하지 않는다.** `POST /charter/generate`와
`POST /document-lion/reviews`는 요청자의 locale로 생성한 결과를 그대로 돌려주므로
이미 요청자의 언어다. 번역이 필요한 것은 **나중에 다른 언어 사용자가 조회할 때**뿐이다.

### 6.4 배치 번역 함수

`app/services/translation.py`에 추가한다.

```python
def call_batch_translation_llm(
    texts: list[str], source_lang: str, target_lang: str
) -> list[str]:
    """여러 텍스트를 한 번의 LLM 호출로 번역한다. 입력과 같은 길이·순서로 반환한다."""
```

- 기존 `call_translation_llm`과 달리 `preserved_terms`를 반환하지 않는다.
  규칙·이슈 응답 스펙에 해당 필드가 없기 때문이다. 다만 고유명사를 원문 유지하라는
  지시는 프롬프트에 동일하게 넣는다.
- **응답 길이가 입력과 다르면 실패로 간주**하고 원문 폴백을 태운다.
  순서가 어긋난 채 매핑되면 엉뚱한 규칙에 엉뚱한 번역이 붙는다.

### 6.5 무효화

규칙은 `PATCH /api/ai/charter/rules/{ruleId}`로 사람이 수정할 수 있다.
원문이 바뀌면 저장된 번역은 거짓이 된다.

- `source_text_hash`가 현재 원문 해시와 다르면 캐시를 무시하고 재번역한다.
  기존 Translation이 쓰는 `source_content_hash` 방식과 동일하다.
- `PATCH`에도 `locale`을 받아 `source_locale`을 갱신한다.
  일본 사용자가 한국어 규칙을 일본어로 고쳐 쓸 수 있기 때문이다.

### 6.6 실패 처리 (D8)

번역 LLM 호출이 실패하면 **예외를 전파하지 않고 원문을 그대로 응답한다.**
조회 화면이 통째로 죽는 것보다 원본 언어라도 보이는 편이 낫다.
실패는 경고 로그로 남긴다. 기존 Translation의 `실패 즉시 원문 표시` 정책과 일치한다.

---

## 7. 마이그레이션

**이 프로젝트에는 Alembic이 없다.** `scripts/create_tables.py`는
`Base.metadata.create_all`을 호출하는데, 이는 **없는 테이블만 생성하고 기존 테이블에 컬럼을
추가하지 않는다.**

따라서:

- `ai_text_translation` 신규 테이블 → `create_all`로 생성된다. 모델만 추가하면 된다.
- `source_locale` 컬럼 2개 → **`create_all`로는 생기지 않는다.** 별도 SQL이 필요하다.

`scripts/migrations/2026-08-21_add_source_locale.sql`에 멱등한 DDL을 둔다.

```sql
ALTER TABLE charter_rule    ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
ALTER TABLE document_review ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
```

> Alembic 도입은 별도 과제로 남긴다. 본 설계의 범위를 넘어서며, 이번 변경은 멱등 DDL 한 개로
> 충분하다. 다만 스키마 변경이 반복되면 도입이 필요하다는 점은 기록해둔다.

---

## 8. BE(Spring) 작업

별도 레포에서 수행한다.

1. `UserEntity.language` 값을 조회해 AI 프록시 호출에 실어 보낸다 (POST 4곳, GET 2곳).
   값이 `null`이면 필드를 생략하거나 `null`로 보내면 된다 — AI가 기본값으로 처리한다(3.4).
2. 코드 매핑은 불필요하다 (3.1 확인 완료).
3. `docs/api_contract.md`를 갱신한다.

> 선택 사항: `UpdateProfileRequest.language`에 `@Pattern` 검증을 추가하면 이상값 유입을
> 원천 차단할 수 있다. 본 설계는 검증이 없는 현재 상태를 전제로 동작하므로 필수는 아니다.

---

## 9. 테스트 전략

| 대상 | 검증 내용 |
|---|---|
| `core/locale.py` | 지원 값 통과 / 미지원 값은 `en` 폴백 / `None`은 `ko` |
| 서비스 3곳 | `locale="ja"` → 프롬프트에 `"Japanese"` 포함 |
| 서비스 3곳 | `locale` 미전달 → 프롬프트에 `"Korean"` 포함 |
| 배치 번역 | 입력과 출력 길이 불일치 시 실패 처리 |
| 조회 번역 | `source_locale`과 요청 locale이 같으면 LLM 미호출 |
| 조회 번역 | 캐시 적중 시 LLM 미호출 |
| 조회 번역 | 해시 불일치 시 재번역 |
| 조회 번역 | LLM 실패 시 원문 응답 + 예외 미전파 |
| 라우트 | `locale` 쿼리 파라미터 누락 시 기본 동작 유지 |

**기존 테스트 수정 대상**: `tests/test_writing_assistant_llm.py::test_prompt_requires_korean_output`.
현재는 "항상 한국어"를 검증하는데, 본 설계 이후 의미가 "기본값이 한국어"로 바뀐다.

---

## 10. 롤아웃 순서

1. `core/locale.py` + 서비스 3곳의 생성 시점 locale 적용 (`locale` optional)
   → 이 시점에 배포해도 BE 변경 없이 현행 동작이 유지된다
2. 마이그레이션 SQL 적용 + `ai_text_translation` 모델 추가
3. 조회 시 번역 구현
4. BE가 locale 전달 시작
5. `api_contract.md` 갱신

1번과 4번 사이에는 언제든 배포 가능한 상태가 유지된다.

---

## 11. 검토했으나 채택하지 않은 대안

### 11.1 FE 브라우저 온디바이스 번역 (Translator API)

6절의 서버 측 조회 시 번역 대신, 브라우저 내장 Translator API로 FE에서 번역하는 안을
검토했다. 채택하면 6·7절(원본 언어 컬럼, 번역 캐시 테이블, 마이그레이션)이 통째로
불필요해지고 API 쿼터도 들지 않아 매력적이었다.

**2026-08-21 조사 결과, 주 경로로는 채택하지 않는다.**

| 항목 | 확인된 사실 |
|---|---|
| 지원 브라우저 | Chrome 138+ / Edge 148+ |
| Firefox · Safari | 미지원 |
| 모바일 | 전 플랫폼 미지원 |
| 용어 보존(glossary) | 기능 없음 |
| 실행 조건 | transient user activation 필요 — 페이지 로드 시 자동 번역 불가 |
| 기타 | Web Worker 사용 불가, 번역 순차 처리, 최초 사용 시 모델 다운로드 |

MDN은 해당 API를 "Baseline이 아니며 널리 쓰이는 일부 브라우저에서 동작하지 않는다"고
명시한다.

**채택하지 않는 이유 세 가지**

1. **커버리지 부족.** Safari 및 모든 모바일에서 동작하지 않는다. "외국 사용자가 기존
   규칙을 읽는다"는 해결 대상 시나리오 자체를 절반 이상 놓친다.
2. **용어 보존 불가.** 이 제품은 `preservedTerms`를 갖춘 "Dev-aware Translation"을
   별도 기능으로 구축했다(`docs/api_contract.md` 1절). 온디바이스로 전환하면
   "Doc PR", "RACI" 같은 도메인 용어가 번역되어 그 설계 판단을 스스로 뒤집는다.
3. **자동 실행 불가.** 사용자 상호작용 이후에만 번역이 시작되므로 조회 화면에서
   자연스럽게 번역된 내용을 보여주는 UX가 성립하지 않는다.

**비용 반박**: 서버 번역의 실제 비용은 낮다. 배치 호출(D7)과 캐시(6.2b) 때문에
"팀 × 대상 언어" 조합당 사실상 1회이며, 규칙이 수정되지 않는 한 재호출이 없다.
온디바이스로 절감되는 쿼터가 위 세 가지 손실을 정당화하지 못한다.

**재검토 조건**: Safari와 모바일이 Translator API를 지원하고, 용어 보존(glossary)
기능이 추가되면 다시 검토할 가치가 있다. 그 시점에는 서버 번역을 유지한 채
지원 브라우저에서만 온디바이스를 쓰는 점진적 향상으로 붙일 수 있다.

### 11.2 신규 가입자 기본 언어를 영어로 고정

`SignupService`가 `language`를 채우지 않는 문제(3.1)의 해법으로, 기본값을 영어로
두는 안을 검토했다. **채택하지 않는다.**

한국어 사용자가 가입 후 프로필을 수정하기 전까지 영어 제안을 받게 되는데, 이는
2026-08-21에 PR #24로 수정한 버그(한국어 문서에 영어 제안이 노출됨)와 사용자
입장에서 동일한 증상이다. 버그로 고친 동작을 설계로 되살리는 셈이다.

대신 **가입 시 `Accept-Language`로 초기값을 잡고, 해석 불가 시 영어로 폴백**하는
안을 권장한다(13절 열린 질문 (b)). 한 단계 로직으로 한국어·일본어·기타 사용자가
자동으로 갈린다.

---

## 12. 범위 밖 (Non-goals)

- **Translation 엔드포인트의 `targetLang` 기본값 변경.** FE가 이미 명시적으로 대상 언어를
  고르는 구조이므로 프로필 locale과 겹칠 필요가 없다.
- **`document_lion.py` 프롬프트의 영어 기반 재작성.** 검토 품질에 영향을 줄 수 있어 별도 과제.
- **Alembic 도입.**
- **사용자가 UI에서 즉석으로 언어를 전환하는 기능.** 프로필 설정을 따른다.
- **지원 언어 확대(중국어 등).** `SUPPORTED_LOCALES`와 `_LANGUAGE_NAMES`에 추가하면 되도록
  설계했으나, 이번 구현에서는 `ko`/`en`/`ja`만 다룬다.

---

## 13. 신규 가입자 기본 언어 — (b)로 확정 (2026-08-21)

`SignupService`가 `language`를 채우지 않아 모든 신규 가입자가 `null`이고, 본 설계상
`null`은 한국어로 처리된다. 즉 일본에서 막 가입한 사용자도 프로필을 직접 바꾸기 전까지는
한국어를 받는다. 검토한 세 안 중 **(b) 가입 시 `Accept-Language`로 초기값, 실패 시 영어**를
채택한다. (a)는 우리가 PR #24로 고친 버그와 방향만 반대인 동일 증상이고, (c)는 가장
정확하지만 온보딩 단계가 하나 늘어난다. (b)를 넣어도 나중에 (c)로 올릴 수 있으나 그 역은
되돌리는 일이 생긴다. 영어 고정안은 별도로 제외했다 (11.2 참고).

### 13.1 확정 스펙 (BE 작업 범위)

| 상황 | 결과 |
|---|---|
| 헤더 없음 / 빈 값 / 공백 | `en` |
| 헤더 포맷이 깨짐 | `en` |
| `ko-KR,ko;q=0.9` | `ko` |
| `ja-JP` | `ja` |
| `en-US` | `en` |
| `zh-CN,ja;q=0.8` | **`ja`** |
| `zh-CN` / `*` | `en` |

핵심은 `zh-CN,ja;q=0.8` 행이다. **첫 토큰이 아니라 q값 순서상 '지원되는' 첫 언어를 잡아야 한다.**
첫 토큰만 보고 미지원이면 폴백하는 구현은 이 케이스에서 일본어를 놓치고 영어를 준다.
중국어 로케일 노트북을 쓰는 일본 사용자가 정확히 이 경우다.

직접 파싱할 필요는 없다. `java.util.Locale`이 RFC 4647 lookup을 이미 구현해뒀다.

```java
private static final List<String> SUPPORTED = List.of("ko", "en", "ja");
private static final String FALLBACK = "en";

String resolveSignupLanguage(String acceptLanguage) {
    if (acceptLanguage == null || acceptLanguage.isBlank()) return FALLBACK;
    try {
        String tag = Locale.lookupTag(Locale.LanguageRange.parse(acceptLanguage), SUPPORTED);
        return tag != null ? tag : FALLBACK;
    } catch (IllegalArgumentException e) {
        return FALLBACK;   // 깨진 헤더
    }
}
```

- `LanguageRange.parse()`가 q값 정렬까지 한다
- `lookupTag()`가 `ko-KR` → `ko` 절단 매칭을 한다 — 서브태그를 직접 자를 필요 없다
- 깨진 헤더는 `IllegalArgumentException`으로 튄다. **잡지 않으면 가입 자체가 500으로 죽는다**

> (b)의 폴백은 `en`이고 AI 쪽 `null` 폴백은 `ko`다. **다른 것이 맞다.** (b)는 "브라우저가 알려준
> 언어를 못 읽은 경우"라 범용값이 맞고, AI의 `null`은 "BE가 아직 안 붙은 구간"이라 하위 호환이
> 맞다. 불일치로 착각하지 말 것.

**기존 사용자는 여전히 `null`이다.** (b)는 신규 가입자만 채운다. 따라서 3.4절의 `null` → `ko`
폴백은 계속 필요하며 제거할 수 없다.

---

## 14. 추가 확정 결정 (2026-08-21)

### 14.1 `locationRef` 포맷 — `{"blockId","quote"}` 객체 (D10)

`document_review_issue.location_ref`는 `Text nullable`이라 포맷 제약이 없었다. 네 가지 안을
검토했다.

| 안 | LLM이 만들 수 있나 | FE 하이라이트 | 계약 변경 |
|---|---|---|---|
| blockId + quote | 블록을 받아야 가능 | 정확 | `ReviewRequest`에 `blocks` |
| 문장 원문 발췌만 | 지금 그대로 | 문자열 검색 — 중복 문장에서 어긋남 | 없음 |
| 문자 오프셋 | **신뢰 불가** | 맞으면 정확 | 없음 |
| 섹션 경로 문자열 | 잘 만듦 | 대략적 위치만 | 없음 |

문자 오프셋은 논외다. LLM은 문자 오프셋을 세지 못하고, 틀린 숫자를 자신 있게 내놓는다.
검증 없이 배포하면 조용히 엉뚱한 곳을 하이라이트한다.

**blockId + quote를 채택한다.** 근거 세 개다.

1. **데이터가 이미 존재한다.** BE는 Translation 호출 때 `blockId`를 이미 보내고 있고
   `blocks` 테이블도 있다. 없는 것을 새로 만드는 게 아니라 이미 보내는 것을 여기에도 보내는 것이다.
2. **발췌만 먼저 하면 FE가 버릴 코드를 쓴다.** 문자열 검색 하이라이트 로직은 나중에 blockId로
   가면 통째로 폐기된다.
3. **`quote`가 있어야 블록 안 위치까지 좁힌다.** `blockId` 하나로는 "이 문단에 문제 있음"까지다.

구현 시 못 박은 것 두 개.

- **`blocks`는 optional이다.** `locale`과 같은 이유 — required면 BE 미배포 구간이 전부 422가 된다.
- **LLM이 만들어낸 존재하지 않는 `blockId`는 버린다.** 전달한 집합에 없으면 제거하고 `quote`만
  남긴다. 검증 없이 저장하면 FE가 없는 블록을 찾다 조용히 실패한다.
- **`quote`는 번역하지 않는다.** 원문 문서를 가리키는 포인터다. 일본 사용자가 조회하면 설명은
  일본어인데 `quote`만 원문 언어로 남는다. 이것이 정상 동작이며, 명시하지 않으면 버그로 신고된다.

LLM에게 JSON 문자열을 만들게 하지 않는다. `block_id`와 `quote`를 구조화된 필드로 받고 저장
직전에 우리가 직렬화한다.

### 14.2 Writing Assistant 제안 그룹핑 — 하지 않는다 (D11)

기본 제안 수가 3개다(`writing_assistant_suggestion_count`). **3개를 3그룹으로 나누면 그룹당
1개**라 그룹핑의 실익이 없다.

그룹핑 논의의 실제 원인은 다른 데 있었다. 프롬프트에 순서 지시가 없어 **응답 순서가 매번
달랐고**, 같은 문서에 두 번 요청하면 UI에서 제안 순서가 뒤바뀌어 보였다.

그래서 평평한 리스트를 유지하고 **서버가 `structure` → `next-paragraph` → `clarity` 순으로
정렬**한다. 계약이 안 바뀌어 FE 수정이 없고, 유형별로 정렬돼 있어 그대로 렌더해도 묶여 보인다.

**정렬은 자르기 이후에 한다.** 순서를 뒤집으면 `structure` 제안만 남도록 편향된다. LLM이 고른
상위 N개를 존중하고 표시 순서만 정돈하는 것이 목적이다.

### 14.3 DocumentLion 모델 등급 — 설정만 분리 (D12)

`settings.gemini_model` 하나를 5곳이 전부 쓰고 있어 **DocumentLion만 모델을 올릴 방법이
없었다.** 올리면 5곳 다 올라간다.

추론 난이도를 보면 판단 계열이 둘이다.

| 기능 | 계열 |
|---|---|
| Translation / Writing Assistant / Charter | 변환·생성 |
| **DocumentLion** (문서 이해 → 규칙 대조 → 위반 판정 → severity → UUID 인용) | **판단** |
| **CIO** (원문 vs 생성물 대조 → 환각·이탈 판정) | **판단** |

CIO도 같은 위험군이라는 점은 기존 문서에 없었다.

**다만 측정된 것이 없다.** Flash-Lite가 충분한지 부족한지 지금 단정하는 것은 양쪽 다 추측이다.
그래서 값은 바꾸지 않고 **설정만 분리**한다 — `document_lion_model` / `cio_model`이 비어 있으면
`gemini_model`을 쓴다. 비용 0, 동작 변화 0이며, 측정 결과가 나오면 `.env` 한 줄로 교체된다.
품질 문제가 실제로 터졌을 때 대응이 배포 1회에서 설정 변경 1회로 줄어든다.

**품질 측정은 별도 과제로 남긴다.** 위반이 있는 문서 3~4개 + 없는 문서 2개로 실호출 6회 정도면
감이 잡힌다. 실제 API 쿼터를 쓰는 일이라 별도 승인 후 진행한다.

### 14.4 배치 번역 청크 — 문자 수 4,000자 (D13)

입력 토큰 한도는 문제가 아니다. 실질 제약은 두 개다.

**출력 한도.** 번역은 출력이 입력과 거의 같은 크기라, 입력 여유가 있어도 출력이 잘리면 실패다.

**All-or-nothing 실패 — 이게 더 위험하다.** 6.4절이 "응답 길이가 입력과 다르면 원문 폴백"을
정했는데(옳은 판단이다), 배치가 커지면 그 폴백의 피해 범위도 같이 커진다. 규칙 30개를 한 번에
보냈다가 개수가 하나 어긋나면 **30개 전부 원문으로 떨어진다.** 즉 **청크 분할은 토큰 대책이
아니라 실패 격리 장치**다.

**개수 기준은 틀린 지표다.** 규칙 5개가 각 2,000자면 10,000자이고, 30개가 각 100자면 3,000자다.

```
누적 문자 수가 4,000자를 넘으면 새 청크로 끊는다.
단일 항목이 4,000자를 넘으면 그 항목 혼자 한 청크가 된다.
실패는 청크 단위로 격리한다 — 실패한 청크만 원문, 나머지는 번역 유지.
```

- 기본 시나리오(규칙 5개, 대략 1,000~2,000자)는 **1청크로 끝나 오버헤드가 0**이다
- 단일 항목 초과를 명시적으로 처리해야 한다. 안 정해두면 빈 청크나 진행되지 않는 루프가 생긴다
- 값은 `translation_batch_chunk_chars` 설정으로 뺐다 — 코드에 숫자를 박지 않는다

**번역 실패 시 원문을 캐시에 저장하지 않는다.** 배치 함수는 실패 시 원문을 되돌려주는데, 그
원문을 번역으로 upsert하면 캐시가 영구히 오염되어 이후 재시도조차 하지 않는다. 번역문이 원문과
같으면 저장을 건너뛴다.
