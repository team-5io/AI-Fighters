# AI 생성 텍스트 다국어(locale) 대응 설계

- 작성일: 2026-08-21
- 상태: 설계 확정 (구현 전)
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

---

## 3. locale 전달 계약

AI-Fighters에는 인증도 BE DB 접근도 없다(`docs/api_contract.md`). 따라서 locale은
**BE가 프록시 호출 시 명시적으로 전달**해야 한다. 다른 경로는 없다.

### 3.1 값 포맷

BCP-47 소문자 코드: `"ko"`, `"en"`, `"ja"`.
Translation 엔드포인트가 이미 `sourceLang: "ko"` / `targetLang: "en"`을 쓰고 있어 그와 통일한다.

> **선행 확인 필요**: BE 프로필의 선호 언어 필드가 실제로 어떤 값을 담는지 확인해야 한다.
> `KOREAN` 같은 enum이나 `한국어` 같은 표시 문자열이라면 BE 쪽에 코드 매핑이 필요하다.

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
| 누락 / `null` | `ko` | 하위 호환 — BE 미배포 구간의 현행 동작 유지 |
| 지원 목록 내 (`ko`/`en`/`ja`) | 그대로 | — |
| 지원 목록 밖 (`th` 등) | `en` + 경고 로그 | 한국어보다 범용적 (D4) |

---

## 4. 공용 locale 모듈 — `app/core/locale.py` (신규)

세 서비스가 각자 언어 지시 문자열을 조립하면 세 벌로 갈라진다. 단일 지점으로 묶는다.

```python
SUPPORTED_LOCALES = frozenset({"ko", "en", "ja"})
DEFAULT_LOCALE = "ko"      # locale 미전달 시
FALLBACK_LOCALE = "en"     # 지원하지 않는 값이 왔을 때

_LANGUAGE_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese"}

def normalize_locale(raw: str | None) -> str:
    """요청에서 받은 locale을 지원 언어로 정규화한다."""

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

1. 사용자 프로필의 선호 언어 값을 조회해 AI 프록시 호출에 실어 보낸다 (POST 4곳, GET 2곳).
2. 프로필 값이 BCP-47 코드가 아니면 `ko`/`en`/`ja`로 매핑한다.
3. `docs/api_contract.md`를 갱신한다.

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

## 11. 범위 밖 (Non-goals)

- **Translation 엔드포인트의 `targetLang` 기본값 변경.** FE가 이미 명시적으로 대상 언어를
  고르는 구조이므로 프로필 locale과 겹칠 필요가 없다.
- **`document_lion.py` 프롬프트의 영어 기반 재작성.** 검토 품질에 영향을 줄 수 있어 별도 과제.
- **Alembic 도입.**
- **사용자가 UI에서 즉석으로 언어를 전환하는 기능.** 프로필 설정을 따른다.
- **지원 언어 확대(중국어 등).** `SUPPORTED_LOCALES`와 `_LANGUAGE_NAMES`에 추가하면 되도록
  설계했으나, 이번 구현에서는 `ko`/`en`/`ja`만 다룬다.

---

## 12. 열린 질문

- BE 프로필 선호 언어 필드의 실제 값 포맷 (3.1 참고) — 확인 후 매핑 필요 여부 결정
- 규칙 목록이 매우 커질 경우 배치 번역 1회의 토큰 한도. 현재 팀당 규칙 수가 적어(기본 5개)
  문제되지 않으나, 규칙이 수십 개로 늘면 청크 분할이 필요하다.
