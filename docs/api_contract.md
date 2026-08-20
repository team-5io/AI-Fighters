# AI-Fighters REST API 계약 (v1)

Base URL: `/api/ai`

**호출 방식 (2026-08-14 확정)**: 아래 엔드포인트는 전부 **BE(Spring)가 게이트웨이로 프록시**한다.
FE는 AI-Fighters를 직접 호출하지 않는다 — Spring이 인증/인가를 처리한 뒤 서버 간으로 AI-Fighters를
호출하고, 결과를 `GlobalApiResponse`로 감싸서 FE에 내려준다. DocumentLion 자동 트리거에만 쓰이던
패턴을 전 도메인으로 확장한 것. 아래 각 엔드포인트의 "트리거"는 이 호출을 최초로 발생시키는
주체(FE 사용자 액션 vs BE 자동)만 나타낸다 — 실제 HTTP 호출 주체는 항상 BE다.

- AI-Fighters 자체에는 인증/인가 로직이 없다 (BE가 전담). 내부망 전용 엔드포인트로 취급한다.
- 아래 요청/응답의 사용자 식별자(`adoptedBy`, `requestedBy` 등)는 BE `UserEntity`의 내부 PK(`Long`)가
  아니라, 외부 노출용으로 별도 발급하는 `publicId`(UUID)다.
- **(2026-08-17 추가)** 아래 세 엔드포인트(Translation/Writing Assistant/DocumentLion)는 결과를 내려주기
  전에 내부적으로 CIO 2차 검토(`AI 제안 결과 2차 검토`, Notion "AI CIO 오케스트레이션")를 거친다. 이건
  순수 내부 로직이라 요청/응답 스펙에는 영향 없고, 검토가 실패해도 원래 응답은 그대로 내려간다 — BE가
  신경 쓸 부분 없음.

**출력 언어 — AI는 항상 영어로 생성한다 (2026-08-21 확정)**

AI가 자연어를 생성하는 세 지점(Writing Assistant 제안, Charter 규칙 초안, DocumentLion 이슈 설명)은
**언제나 영어로 출력한다.** 사용자 언어로의 번역은 **FE가 브라우저 온디바이스 번역으로 처리한다.**

- **요청에 `locale` 같은 언어 필드가 없다.** BE는 사용자 언어를 AI로 보내지 않아도 된다.
- 저장되는 텍스트(Charter 규칙, DocumentLion 이슈)도 영어로 저장된다. 서버는 번역하지 않는다.
- 사용자가 언어를 설정하기 전에는 영어가 그대로 보인다. 의도된 동작이다.

> Translation 엔드포인트(1절)는 **별개 기능이다.** 그건 사용자가 명시적으로 문서 블록을 번역하는
> 기능이고 `sourceLang`/`targetLang`을 그대로 받는다. AI 생성 텍스트의 출력 언어와 무관하다.

> 이전 판에는 `locale`을 받아 사용자 언어로 생성하고 조회 시 서버가 번역하는 설계가 적혀 있었다.
> 온디바이스 번역으로 방향이 바뀌면서 전부 제거했다.

---

## 1. Dev-aware Translation

### `POST /api/ai/translations`
트리거: **FE** (사용자 요청) → BE 프록시

**(2026-08-18 변경)** 문서 본문이 블록 구조로 바뀌면서, 문서 전체가 아니라 **블록 하나당 한 번씩** 호출한다
(`type: "code"`인 블록은 번역 대상에서 제외 — BE가 원문 그대로 유지하고 호출하지 않음). 원문 내용은 FE가
이미 들고 있는 걸 그대로 전달한다 (AI-Fighters가 BE DB를 직접 조회하지 않음).

```json
// Request
{
  "documentId": 42,
  "blockId": "string",
  "content": "string",
  "sourceLang": "ko",
  "targetLang": "en"
}

// Response 200
{
  "translatedContent": "string",
  "preservedTerms": ["Doc PR", "RACI"],
  "cached": false
}
```

- `documentId`는 BE `Document`의 내부 PK(`Long`)를 그대로 쓴다 — 다른 엔드포인트의 `uuid`(`publicId`)와
  달리 document는 별도 publicId가 없다. `blockId`는 BE `blocks` 테이블의 FE 생성 문자열 id.
- 캐시는 서버 내부에서 `documentId + blockId + targetLang` 기준으로 처리 (`translation_cache` 테이블,
  블록 단위로 세분화하기 전에는 `documentId + targetLang`만으로 유니크했음 — 블록별 호출로 바뀌면서
  두 번째 블록부터 UniqueConstraint 위반이 나던 문제를 이렇게 해결). FE는 캐시 여부를 신경 쓸 필요 없음,
  응답의 `cached` 필드만 참고.
- 실패 시 `502` + `{ "error": "translation_failed" }` → FE는 원문을 그대로 보여주면 됨. **재시도 버튼을 붙일지는 아직 미확정** (아래 열린 질문 참고), 일단은 실패 즉시 원문 표시로 구현.

---

## 2. AI Writing Assistant

### `POST /api/ai/writing-assistant/suggestions`
트리거: **FE** (작성자가 버튼/단축키로 명시적 요청할 때만) → BE 프록시

```json
// Request
{
  "documentId": 42,
  "content": "string",
  "cursorContext": "string"
}

// Response 200
{
  "suggestions": [
    { "type": "structure", "text": "string" },
    { "type": "next-paragraph", "text": "string" },
    { "type": "clarity", "text": "string" }
  ]
}
```

> **(2026-08-21 확정)** 응답은 유형별로 묶지 않고 평평한 리스트를 유지한다. 대신 서버가
> `structure` → `next-paragraph` → `clarity` 순으로 **정렬해 내려준다**(큰 단위에서 작은 단위로).
> 프롬프트에 순서 지시가 없어 LLM 응답 순서가 매번 달라졌고, 같은 문서에 두 번 요청하면 UI에서
> 제안 순서가 뒤바뀌어 보였다. 필드는 그대로이므로 FE 수정은 없다. 유형별 묶음이 필요하면
> `type`으로 group by 하면 된다. 제안 목록만 내려오며 저장은 FE가 수락한 항목만 본문에 반영.
>
> `structure` 타입은 Notion "문서 구조 가이드 제안" 스펙대로 문서에 필요한 목차·필수 섹션 구조(빠진 섹션, 순서 재배치 등)를 추천한다. "관련 문서 맥락 인용 지원"(Document Graph 연동)은 별도 기능이며 아직 BE에 그 API가 없어 미구현.
>
> **(2026-08-19 수정)** `documentId`는 BE `Document.id`(`Long`) — 다른 엔드포인트와 마찬가지로 별도 publicId 없음. 응답에는 안 쓰이고 로그용으로만 참조된다.

---

## 3. DocumentLion

### `POST /api/ai/document-lion/reviews`
트리거: **FE**(검토 버튼) 또는 **자동**(Doc PR 제출 시) — 둘 다 BE 프록시

```json
// Request
{
  "documentId": 42,
  "docPrId": 7,               // number | null
  "teamId": 1,                // (2026-08-17 추가) 채택된 Charter 규칙 조회용 — 협업 규칙 위반 검토에 필수
  "triggerType": "manual",    // "manual" | "auto"
  "requestedBy": "uuid",      // auto 호출 시에도 필수 — BE가 Doc PR 제출자의 publicId(userId)를 채워서 보낸다
  "content": "string",        // (2026-08-17 추가) 문서 본문 — AI가 BE DB를 직접 조회하지 않으므로 필수
  "blocks": [                 // (2026-08-21 추가) optional — 주면 이슈 위치를 blockId로 정확히 짚는다
    { "blockId": "string", "content": "string" }
  ],
  "relatedDocuments": [       // (2026-08-21 추가) optional — conflict/inconsistency 검토용
    {
      "documentId": 200,
      "title": "string",
      "content": "string",
      "relationType": "REFERENCE",
      "direction": "OUTGOING"   // optional
    }
  ]
}

// Response 200
{
  "reviewId": "uuid",
  "overallVerdict": "reject_recommended",
  "issues": [
    {
      "severity": "critical",     // "critical" | "medium" | "minor"
      "issueType": "conflict",    // "conflict" | "inconsistency" | "charter_violation"
      "description": "string",
      "relatedDocumentId": 42,
      "charterRuleId": null,
      "locationRef": {              // (2026-08-21 변경) 문자열 -> 객체
        "blockId": "string",        // string | null
        "quote": "string"           // string | null — 문제 문장의 원문 발췌
      }
    }
  ]
}
```

- **(2026-08-19 수정)** `documentId`/`docPrId`/`teamId`/`relatedDocumentId`는 BE의 내부 PK(`Long`)를 그대로 쓴다 — Document/DocPr/Team은 `requestedBy`(userId)와 달리 별도 publicId가 없다. 예전엔 전부 `uuid`로 잘못 잡혀있었음(Translation의 `documentId` 버그와 동일 유형).
- `overallVerdict`는 `issues`에 `critical`이 하나라도 있으면 `reject_recommended`, 없으면 `approve`.
- Doc PR이 "리뷰 대기" 상태로 바뀌는 시점에 BE가 이 엔드포인트를 `triggerType: "auto"`로 호출한다.
- **(2026-08-21 추가) `blocks`와 `locationRef`.** `blocks`를 보내면 프롬프트가 블록 단위로 렌더링되고
  이슈의 `locationRef.blockId`에 해당 블록 id가 담긴다 — FE가 정확히 스크롤·하이라이트할 수 있다.
  Translation 엔드포인트가 이미 쓰는 `blockId`(BE `blocks` 테이블의 FE 생성 문자열 id)와 같은 값이다.
  `blocks`를 생략하면 기존처럼 `content` 평문으로 검토하고 `blockId`는 `null`이 된다.
  `quote`는 문제 문장의 원문 발췌로, `blockId`만으로는 짚히지 않는 블록 안 위치를 좁혀준다.
  AI가 전달받은 집합에 없는 `blockId`를 만들어내면 버린다 — 없는 블록을 찾다 실패하는 것을 막는다.
  `quote`는 원문 문서에서 그대로 발췌한 문장이다. 이슈 `description`은 영어인데 `quote`는 문서
  원문 언어로 남는다 — 원문을 가리키는 포인터이므로 정상이다. FE가 온디바이스 번역을 걸 때도
  `quote`는 제외해야 한다. 번역하면 문서에서 그 문장을 찾을 수 없다.
- **(2026-08-21 정정) `conflict`/`inconsistency`는 `relatedDocuments`를 받으면 검토한다.**
  이전 판에는 "BE의 `GET /documents/{id}/graph`가 없어서 항상 이슈 없음"이라고 적혀 있었다.
  **`/graph`는 존재하지 않는 이름이었다.** 실제 API는 `GET /documents/{documentId}/relations`이며
  BE `72efa68`(2026-08-17)로 이미 들어가 있다. 없는 이름을 찾고 있어서 생긴 오기였다.

  다만 `/relations` 응답에는 **이웃 문서 본문이 없다** — `relationId`, `direction`, `relationType`,
  `neighborDocumentId`, `neighborTitle`, `createdAt`뿐이다. 그래서 그 응답만 프록시해서는 검토가
  불가능하다. **BE가 이웃 문서 본문까지 조회해 `relatedDocuments`로 실어 보내야 한다.**
  Charter 규칙·문서 본문을 BE가 실어 보내는 기존 패턴과 동일하며, AI가 BE를 직접 호출하지 않으므로
  서비스 토큰 체계를 새로 만들 필요가 없다.

  `relatedDocuments`를 생략하면 `conflict`/`inconsistency`는 이슈 없음으로 나오고
  `charter_violation`만 검사한다 — 기존 동작과 같다.

  `documentId`는 BE `Document.id`(`Long`)다. AI가 만들어낸 존재하지 않는 id는 저장 단계에서
  버린다(`relatedDocumentId`가 `null`이 된다) — 없는 문서를 FE가 찾다 실패하는 것을 막는다.

### `GET /api/ai/document-lion/reviews/{reviewId}`
트리거: **FE** (리뷰 화면 재진입 시 결과 다시 조회) → BE 프록시

```json
// Response 200 — 위 POST 응답과 동일 형태
```

- 저장된 그대로 내려준다. 이슈 `description`은 영어다. 번역은 FE 담당.

---

## 4. Team Collaboration Charter

> `charter_rule` 테이블은 규칙 하나하나가 각자 `id`를 가진 독립 행이고, 여러 규칙을 묶는 "Charter" 상위 엔티티는 ERD에 따로 없다. 그래서 아래 API도 규칙 단위로 조작하고, 채택만 팀 단위 일괄 처리로 뺐다 (이전 초안은 없는 `charterId`를 상위 리소스로 쓰고 있어서 여기서 고쳤다).

### `POST /api/ai/charter/generate`
트리거: **FE** (팀 생성 초기 1회) → BE 프록시
```json
// Request  { "teamId": 1 }
// Response { "rules": [{ "id": "uuid", "status": "draft", "title": "string", "description": "string" }] }
```
- **(2026-08-19 수정)** `teamId`는 BE `Team.id`(`Long`) — 예전엔 `uuid`로 잘못 잡혀있었음. 규칙 `id`는 AI-Fighters 자체 PK라 그대로 `uuid`.

### `PATCH /api/ai/charter/rules/{ruleId}`
트리거: **FE** — 규칙 하나 수정 → BE 프록시
```json
// Request { "title": "string", "description": "string" }
```

### `POST /api/ai/charter/adopt`
트리거: **FE** — 지정한 규칙들을 공식 규칙으로 일괄 채택 (이후 DocumentLion 검토 기준으로 사용) → BE 프록시
```json
// Request { "teamId": 1, "ruleIds": ["uuid"], "adoptedBy": "uuid" }
```

### `GET /api/ai/charter/rules?teamId=1`
트리거: **FE** — 현재 팀의 규칙 목록 조회 (draft·adopted·archived 전체, `status`로 필터 가능) → BE 프록시

- 저장된 그대로 내려준다. `title`·`description`은 영어다. 번역은 FE 담당.

---

## 열린 질문 (구현 중 확정 필요)

- 번역 실패 시 재시도 버튼을 둘지, 즉시 원문 표시만 할지
- Writing Assistant 제안 개수 제한 (한 번에 몇 개까지 내려줄지)

### 확정된 항목 (2026-08-21)

- **AI 출력 언어**: **항상 영어.** 사용자 언어 번역은 FE 온디바이스가 담당한다. 서버에 `locale` 없음.
- **Writing Assistant 유형별 묶음**: 묶지 않는다. 평평한 리스트 + 서버 정렬로 해결 (2절 참고).
- **DocumentLion `locationRef` 포맷**: `{"blockId", "quote"}` 객체 (3절 참고).
  `quote`는 FE 번역 대상에서 제외할 것.
- **신규 사용자가 보는 언어**: 영어. 별도 기본값 설정이 필요 없어졌다 — BE `SignupService`에
  `Accept-Language` 처리를 넣기로 했던 계획도 함께 폐기한다.
