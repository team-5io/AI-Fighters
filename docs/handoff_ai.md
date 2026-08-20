# AI 파트 인수인계

담당: 김민섭 (AI)

## 버전 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.0.0 | 2026-08-10 | 최초 작성 — Translation 캐시 레이어 작업(#2, #3) 기준 |
| v2.0.0 | 2026-08-21 | Writing Assistant 영어 출력 버그 수정(#24) 및 다국어(locale) 대응 설계(#26) 반영. 전면 재작성 |
| v2.1.0 | 2026-08-21 | 미결정 6건 확정 및 **AI 구현 완료** 반영. 6절이 "정할 것"에서 "결정 완료"로 바뀜 |

> v1.0.0 본문은 현재 상태와 어긋나는 내용(테스트 0개, `google-genai==2.17.0` 등)이 있어
> v2.0.0에서 대체했다. 원문이 필요하면 git 히스토리에서 확인할 것.

---

# 1. 현재 상태 요약 (2026-08-21)

| 항목 | 상태 |
|---|---|
| 테스트 | **174 passed** (`.venv/bin/python -m pytest -q`) — v2.0.0 시점 56개에서 118개 추가 |
| LLM | `gemini-flash-lite-latest`, `google-genai==1.47.0` |
| 배포 | main push 시 CI가 자동으로 build → EC2 deploy (`.github/workflows/ci.yml`) |
| PR #24 | **머지 완료** (main까지 반영) |
| PR #26 | **OPEN** — 설계 문서 + 인수인계서. 결정 6건 반영 완료 |
| 미결정 사항 | **없음.** 6건 전부 확정 (6절) |
| AI 구현 | **완료.** `feature/ai-output-locale` 브랜치, 커밋 6개. PR 미생성 |
| BE 작업 | **미착수** (7절) |
| FE 확인 | **미착수** — 2건 (7.3절) |
| 실제 API 호출 | 구현 중 0회 — 전부 mock |

## 1.1 AI 구현 브랜치

`feature/ai-output-locale` (`origin/develop` 기준, `--no-track`). 커밋 6개.

| 커밋 | 내용 |
|---|---|
| `77a0786` | `app/core/locale.py` + 서비스별 모델 설정 |
| `24854f6` | 서비스 3곳에 생성 시점 locale 적용 |
| `727855a` | DocumentLion `blocks` + `locationRef` |
| `4483075` | `source_locale` 컬럼 + `ai_text_translation` + 마이그레이션 SQL |
| `f6b596b` | 배치 번역 + 문자 수 청크 |
| `3828183` | 조회 시 번역 (GET 2곳) |
| `33b6db9` | `api_contract.md` 갱신 |

**PR을 아직 만들지 않았다.** PR #26 머지 후 올리는 것이 순서상 깔끔하다.

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
| D9 | 신규 가입자는 **`Accept-Language`, 실패 시 `en`** | 온보딩 단계 없이 자동 분기 |
| D10 | `locationRef`는 **`{"blockId","quote"}` 객체** | 제품이 이미 블록 단위로 서 있음 |
| D11 | 제안은 **평평한 리스트 + 서버 정렬** | 계약 변경 없이 순서 불안정만 해결 |
| D12 | DocumentLion·CIO **모델 설정만 분리** | 측정 전에 값을 바꾸지 않음 |
| D13 | 배치 번역 청크 **문자 수 4,000자** | 개수로는 길이 편차를 못 잡음 |

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

1·3번은 설계의 폴백 규칙(3.2)이 흡수한다. **세 개 모두 6절에서 결정이 났다.**

- 2번(가입 시 미기입) → `Accept-Language` 초기값 (결정 1번)
- 3번(검증 없음) → `Language` enum 전환 (결정 2번)
- 1번(nullable)은 그대로 둔다. 기존 사용자가 `null`로 남아 있어 **AI의 `null` → `ko` 폴백은
  계속 필요하다**

구체적인 BE 작업 지시는 **7절**에 있다. `api_contract.md`는 AI 쪽에서 이미 갱신했다.

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

## 5.4 기존 테스트 두 개를 갱신했다 (처리 완료)

`tests/test_writing_assistant_llm.py`의 두 개가 구현 과정에서 의미가 바뀌어 함께 고쳤다.

- `test_prompt_requires_korean_output` → `test_prompt_defaults_to_korean_when_locale_missing`.
  "항상 한국어"에서 "미전달 시 한국어"로 바뀌었다.
- `test_returns_suggestions_from_llm` — LLM 응답 순서 그대로를 검증하고 있었다. D11의 서버
  정렬 때문에 표시 순서를 검증하도록 고쳤다.

**동작을 의도적으로 바꿨기 때문에 갱신한 것이다.** 테스트를 통과시키기 위해 기대값을 낮춘 것이
아니라는 점을 기록해둔다.

## 5.5 번역 실패 결과를 캐시에 저장하면 안 된다

`call_batch_translation_llm`은 실패 시 **원문을 그대로 되돌려준다**(D8). 이 값을 그대로
`ai_text_translation`에 upsert하면 캐시가 영구히 오염되어 **이후 재시도조차 하지 않는다.**

구현에서는 번역문이 원문과 같으면 저장을 건너뛴다. 이 로직을 건드릴 때 주의할 것.

---

# 6. 결정 완료 (2026-08-21) — 미결정 사항 없음

v2.0.0에서 "회의에서 정할 것"으로 남겨둔 항목과, 당시 9절에 흩어져 있던 미확정 항목을 전부 정리했다.
상세 근거는 설계 문서 13·14절에 있다.

| # | 항목 | 결정 | 주체 |
|---|---|---|---|
| 1 | 신규 가입자 기본 언어 | `Accept-Language` → `ko`/`en`/`ja`, 실패 시 `en` | BE |
| 2 | `UpdateProfileRequest.language` 검증 | `Language` enum 전환 + `AttributeConverter` | BE |
| 3 | `locationRef` 포맷 | `{"blockId","quote"}` 객체, `blocks` optional | AI 완료 / BE·FE |
| 4 | 제안 유형별 그룹핑 | 안 함. 평평한 리스트 + 서버 정렬 | AI 완료 |
| 5 | DocumentLion 모델 등급 | 설정만 분리, 값은 유지 | AI 완료 |
| 6 | 배치 번역 청크 | 문자 수 4,000자 | AI 완료 |

## 6.1 1번에 대해 알아둘 것

**AI 코드는 (a)/(b)/(c) 어느 쪽이든 동일하다.** AI가 받는 값은 `"ja"` 아니면 `null`이고
폴백 규칙이 둘 다 흡수한다. 그래서 이 결정을 기다리지 않고 AI 구현을 먼저 끝냈다.

**기존 사용자는 여전히 `null`이다.** 1번은 신규 가입자만 채운다. 3.2절의 `null` → `ko`
폴백은 계속 필요하며 **제거할 수 없다.**

## 6.2 2번(enum)의 비용을 알고 고른 것

enum으로 가면 **지원 언어 추가 시 BE 배포가 항상 강제된다.** 중국어를 붙이려면 AI 배포
하나로는 안 되고 BE enum 수정 + 배포가 세트로 따라온다. 대신 AI가 받는 값이 `ko`/`en`/`ja`/
`null` 넷뿐임이 보장되어 AI 폴백이 진짜 방어선으로만 남는다.

**enum 구현의 함정 3개는 7.2절에 따로 적어뒀다.** 특히 `@Enumerated(EnumType.STRING)`을
쓰면 기존 행에서 500이 난다.

---

# 7. BE·FE 작업 지시

AI는 전부 배포 가능한 상태다. 아래 작업은 **순서에 상관없이** 붙일 수 있다 —
`locale`과 `blocks`가 모두 optional이고, AI 스키마가 미지의 필드를 무시한다
(`CamelModel`에 `extra="forbid"`가 없다). 먼저 배포해도 나중에 배포해도 깨지지 않는다.

## 7.1 BE — 값 전달

**(1) `UserEntity.language`를 AI 프록시 호출에 실어 보낸다.** 생성 계열은 요청 바디,
조회 계열은 쿼리 파라미터다.

| 메서드 | 경로 | 위치 |
|---|---|---|
| POST | `/api/ai/writing-assistant/suggestions` | 바디 `locale` |
| POST | `/api/ai/document-lion/reviews` | 바디 `locale` |
| POST | `/api/ai/charter/generate` | 바디 `locale` |
| PATCH | `/api/ai/charter/rules/{ruleId}` | 바디 `locale` |
| GET | `/api/ai/charter/rules` | 쿼리 `locale` |
| GET | `/api/ai/document-lion/reviews/{reviewId}` | 쿼리 `locale` |

**값이 `null`이면 필드를 생략하거나 `null`로 보내면 된다.** AI가 기본값으로 처리한다.
코드 매핑은 불필요하다 — `UserEntity.language`가 이미 BCP-47 코드다 (4절 확인 완료).

**(2) 가입 시 `Accept-Language`로 `language` 초기값을 채운다** (D9).
확정 스펙과 Java 구현은 **설계 문서 13.1절**에 있다. 요약하면 `Locale.lookupTag()`를 쓰고,
깨진 헤더의 `IllegalArgumentException`을 반드시 잡아야 한다 — 안 잡으면 가입이 500으로 죽는다.

**(3) DocumentLion 호출에 `blocks`를 함께 보낸다** (D10).
`[{ "blockId": "...", "content": "..." }]` 형태다. **Translation 호출에서 이미 보내는
`blockId`와 같은 값**이므로 새로 만들 데이터가 아니다. 생략하면 기존처럼 `content` 평문으로
검토하고 `locationRef.blockId`가 `null`이 된다.

**(4) DocumentLion 호출에 `relatedDocuments`를 실어 보낸다.**

**(2026-08-21 정정)** 이전 판에는 "`GET /documents/{id}/graph`가 없어서 검토가 안 된다"고
적혀 있었다. **`/graph`는 존재하지 않는 이름이었다.** 실제 API는
`GET /documents/{documentId}/relations`이고 BE `72efa68`(2026-08-17)로 이미 들어가 있다.
BE 인수인계서(`handoff_be_ai_integration.md`)에도 같은 오기가 있다 — 그쪽도 고쳐야 한다.

없는 이름을 찾고 있었던 탓에 `conflict`/`inconsistency`가 실재하지 않는 블로커로 오래 막혀
있었다. AI 쪽 구현은 끝냈다.

BE가 할 일은 두 단계다.

1. `GET /documents/{documentId}/relations`로 이웃 문서를 찾는다
2. **이웃 문서 본문까지 조회해서** `relatedDocuments`로 실어 보낸다

2단계가 필요한 이유: `/relations` 응답에 본문이 없다. `relationId`, `direction`,
`relationType`, `neighborDocumentId`, `neighborTitle`, `createdAt`뿐이다. 그 응답을 그대로
프록시하면 AI가 검토할 내용이 없다.

```json
"relatedDocuments": [
  { "documentId": 200, "title": "...", "content": "...", "relationType": "REFERENCE", "direction": "OUTGOING" }
]
```

optional이다. 생략하면 `charter_violation`만 검사하는 기존 동작이 유지된다.
`direction`도 optional이지만 BE가 이미 돌려주는 값이라 같이 보내면 판정 품질에 도움이 된다.

## 7.2 BE — `Language` enum 전환 (결정 2번)

`UpdateProfileRequest.language`에 검증이 없어 `"KO"`, `"Korean"`, `"asdf"`가 그대로 저장된다.
enum 타입으로 전환하기로 정했다. **함정이 세 개 있고, 첫 번째가 가장 위험하다.**

```java
public enum Language {
    KO("ko"), EN("en"), JA("ja");

    private final String code;
    Language(String code) { this.code = code; }

    @JsonValue public String getCode() { return code; }
}
```

### 함정 1 — `@Enumerated(EnumType.STRING)`을 쓰면 기존 행에서 500이 난다

`EnumType.STRING`은 DB에 `"KO"` **대문자**로 저장한다. 기존 행에는 `"ko"` **소문자**가 들어
있다. 읽는 순간 `IllegalArgumentException`이 터지고 **그 사용자의 프로필 조회가 500이 된다.**

`AttributeConverter`를 쓴다. 대문자화 마이그레이션보다 낫다 — 소문자 `ko`가 BCP-47 표기이고
AI로 그대로 넘길 수 있다.

```java
@Converter(autoApply = true)
public class LanguageConverter implements AttributeConverter<Language, String> {
    @Override public String convertToDatabaseColumn(Language l) {
        return l == null ? null : l.getCode();
    }
    @Override public Language convertToEntityAttribute(String db) {
        if (db == null || db.isBlank()) return null;
        for (Language l : Language.values()) {
            if (l.getCode().equalsIgnoreCase(db)) return l;
        }
        return null;   // 함정 2
    }
}
```

### 함정 2 — 이미 DB에 있는 쓰레기 값

검증이 없던 기간에 `"Korean"`, `"asdf"` 같은 값이 들어갔을 수 있다. converter가 이걸 만나
예외를 던지면 **그 사용자의 모든 조회가 500이다.** 위 코드처럼 **모르는 값은 `null`로 관용
처리**해야 한다. `null`은 AI에서 `ko`로 폴백되니 안전하게 착지한다.

배포 전에 실제 오염 상태를 확인해두면 좋다.

```sql
SELECT language, COUNT(*) FROM users GROUP BY language;
```

### 함정 3 — 요청 역직렬화 엄격도

enum이면 `"ko-KR"`이나 `"KO"`가 오면 400이다. FE 언어 선택이 드롭다운이면 문제없고,
자유 입력이면 `@JsonCreator`로 정규화를 넣어야 한다. **7.3절 FE 확인 항목과 연결된다.**

> 참고: **AI 쪽은 enum과 무관하게 관대하게 흡수한다.** `normalize_locale()`이 `"KO"`,
> `"ko-KR"`, `"Korean"`을 전부 받아 정규화하거나 영어로 폴백한다. enum은 DB를 깨끗하게
> 유지하기 위한 것이고, AI 폴백은 제거되지 않는다.

## 7.3 FE 확인 2건

둘 다 AI 구현을 막지 않는다. 확인되면 그에 맞춰 조정한다.

1. **에디터가 블록 기반인가.** `locationRef`를 `blockId` 기준으로 잡았다. 계약에 `blockId`를
   FE가 생성한다고 되어 있어 블록 기반으로 추정했으나, **FE 코드를 직접 본 것은 아니다.**
   블록 기반이면 `blockId`로 스크롤·하이라이트하면 되고, 추가 작업은 거의 없다.
2. **프로필 언어 선택이 드롭다운인가.** 자유 입력이면 7.2절 함정 3 처리가 필요하다.

## 7.4 FE에 알려둘 변경 2건

- **`locationRef`가 문자열에서 객체로 바뀐다.** `{"blockId": string|null, "quote": string|null}`.
  포맷 확정 전에 저장된 행은 `{"blockId": null, "quote": "<원래 문자열>"}`로 내려온다 — 깨지지 않는다.
- **`quote`는 번역되지 않는다.** 원문 문서를 가리키는 포인터라서다. 설명이 일본어인데 `quote`만
  한국어인 것이 **정상**이다.

---

# 8. 검토했으나 채택하지 않은 대안

동일한 논의가 반복되지 않도록 기록해둔다. 상세는 설계 문서 11절 참고.

## 8.1 FE 브라우저 온디바이스 번역 (Translator API)

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

## 8.2 신규 가입자 기본값을 영어로 고정

한국어 사용자가 프로필 수정 전까지 영어 제안을 받게 되는데, 이는 PR #24로 수정한
버그와 **사용자 입장에서 동일한 증상**이다. 버그로 고친 동작을 설계로 되살리는 셈이라
제외했다. 대신 (b) `Accept-Language` 안을 권장한다.

---

# 9. 다음 작업 순서

1. **PR #26 머지** (설계 문서 + 인수인계서) — 결정 6건 반영 완료, 리뷰만 남음
2. **`feature/ai-output-locale` PR 생성 → 리뷰 → develop 머지**
3. **배포 시 마이그레이션 SQL 실행** ← 가장 위험한 단계 (5.1절)
   ```
   scripts/migrations/2026-08-21_add_source_locale.sql
   ```
   `ai_text_translation`은 `create_all`로 생기지만 `source_locale` 두 컬럼은 **안 생긴다.**
   빠뜨리면 조회에서 터진다.
4. **BE 작업** (7절) — 순서 무관, AI가 이미 배포돼 있어도 현행 동작이 유지된다
5. **FE 확인 2건** (7.3절)
6. DocumentLion 모델 품질 측정 — 별도 승인 후 (설계 14.3절)

2번과 4번 사이에는 언제든 배포 가능한 상태가 유지된다. `locale`과 `blocks`가 모두 optional이고
AI 스키마가 미지의 필드를 무시하므로(`CamelModel`에 `extra="forbid"` 없음) **배포 순서가
양방향으로 안전하다.**

---

# 10. 남아 있는 이전 과제

v1.0.0에서 넘어온 것 중 아직 유효한 항목.

- **DocumentLion `conflict`/`inconsistency`** — **AI 구현 완료.** BE가 `relatedDocuments`를
  실어 보내면 동작한다 (7.1절 (4)). 이전 판의 "`/graph`가 없어서 미구현"은 오기였다
- **Writing Assistant 제안 개수 제한 미확정** — 현재 기본 3개(`writing_assistant_suggestion_count`)
- **번역 실패 시 재시도 버튼 여부 미확정** — 현재는 즉시 원문 표시
- **Alembic 도입** — 설계 7절에서 별도 과제로 밀어둠. 스키마 변경이 반복되면 필요
- **`document_lion.py` 프롬프트 영어 기반 재작성** — 설계 12절에서 범위 밖

> `locationRef` 포맷, 제안 유형별 그룹핑, Flash-Lite 적정성은 **6절에서 확정**됐다.

---

# 11. 링크

- 설계 문서: [`docs/superpowers/specs/2026-08-21-ai-output-locale-design.md`](superpowers/specs/2026-08-21-ai-output-locale-design.md)
  — 결정 근거는 13·14절
- PR #24 (머지됨): https://github.com/team-5io/AI-Fighters/pull/24
- PR #26 (OPEN): https://github.com/team-5io/AI-Fighters/pull/26
- AI 구현 브랜치: `feature/ai-output-locale` (PR 미생성, 1.1절 참고)
- 마이그레이션 SQL: `scripts/migrations/2026-08-21_add_source_locale.sql`
  — **배포 시 실행 필수** (5.1절)
- 신규 모듈: `app/core/locale.py`, `app/services/ai_text_translation.py`,
  `app/models/ai_text_translation.py`
- API 계약: [docs/api_contract.md](api_contract.md)
- 배포: [docs/deploy.md](deploy.md)
- ERD: [docs/erd_ai_domain.sql](erd_ai_domain.sql)
- BE 레포: https://github.com/team-5io/BACK-Fighters
