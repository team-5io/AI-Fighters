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
  "documentId": "uuid",
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

> `type`으로 유형 태그를 구분해서 내려준다. **다만 이걸 사이드 패널에서 유형별로 묶어 보여줄지, 구분 없이 목록으로만 보여줄지는 아직 성민과 확정 안 됐다** (아래 열린 질문 참고) — API 응답 필드는 어느 쪽으로 가든 그대로 쓸 수 있게 잡아뒀다. 제안 목록만 내려오며 저장은 FE가 수락한 항목만 본문에 반영.
>
> `structure` 타입은 Notion "문서 구조 가이드 제안" 스펙대로 문서에 필요한 목차·필수 섹션 구조(빠진 섹션, 순서 재배치 등)를 추천한다. "관련 문서 맥락 인용 지원"(Document Graph 연동)은 별도 기능이며 아직 BE에 그 API가 없어 미구현.

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
  "content": "string"         // (2026-08-17 추가) 문서 본문 — AI가 BE DB를 직접 조회하지 않으므로 필수
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
      "locationRef": "string"
    }
  ]
}
```

- **(2026-08-19 수정)** `documentId`/`docPrId`/`teamId`/`relatedDocumentId`는 BE의 내부 PK(`Long`)를 그대로 쓴다 — Document/DocPr/Team은 `requestedBy`(userId)와 달리 별도 publicId가 없다. 예전엔 전부 `uuid`로 잘못 잡혀있었음(Translation의 `documentId` 버그와 동일 유형).
- `overallVerdict`는 `issues`에 `critical`이 하나라도 있으면 `reject_recommended`, 없으면 `approve`.
- Doc PR이 "리뷰 대기" 상태로 바뀌는 시점에 BE가 이 엔드포인트를 `triggerType: "auto"`로 호출한다.
- **(2026-08-17 기준 제약)** `issueType: "charter_violation"`만 실제로 검사한다. `"conflict"`/`"inconsistency"`는 BE의 문서 관계 그래프 조회 API(`GET /documents/{id}/graph`)가 아직 없어서 항상 이슈 없음으로 나온다 — 그 API 준비되면 연동 예정.

### `GET /api/ai/document-lion/reviews/{reviewId}`
트리거: **FE** (리뷰 화면 재진입 시 결과 다시 조회) → BE 프록시

```json
// Response 200 — 위 POST 응답과 동일 형태
```

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

---

## 열린 질문 (구현 중 확정 필요)

- 번역 지원 언어 범위 — 한/영 우선 vs 다국어
- 번역 실패 시 재시도 버튼을 둘지, 즉시 원문 표시만 할지
- Writing Assistant 제안을 유형별로 묶어 보여줄지, 구분 없이 목록으로만 보여줄지
- Writing Assistant 제안 개수 제한 (한 번에 몇 개까지 내려줄지)
- DocumentLion `locationRef` 포맷 — 에디터가 문장/섹션을 식별하는 방식에 맞춰 FE와 맞출 것
