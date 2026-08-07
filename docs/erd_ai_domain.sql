-- ============================================================
-- Doc PR — AI-Fighters 도메인 ERD (초안)
-- 범위: Team Collaboration Charter / DocumentLion / Dev-aware Translation / AI Writing Assistant
-- BE(Spring)가 소유한 document, doc_pr, user, team 등은 별도 DB(마이크로서비스)이므로
-- FK 제약 없이 UUID 값만 참조로 들고 있습니다 (컬럼명 끝에 _ref로 표시).
-- ERDCloud 임포트용 PostgreSQL DDL.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------
-- 1. Team Collaboration Charter
-- ------------------------------------------------------------
CREATE TABLE charter_rule (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_ref        UUID NOT NULL,                     -- BE team.id 참조
    title           VARCHAR(200) NOT NULL,
    description     TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'adopted', 'archived')),
    generated_by    VARCHAR(20) NOT NULL DEFAULT 'ai'
                        CHECK (generated_by IN ('ai', 'user')),
    adopted_by_ref  UUID,                               -- BE user.id 참조 (채택한 사람)
    adopted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_charter_rule_team ON charter_rule (team_ref, status);

-- ------------------------------------------------------------
-- 2. DocumentLion — 검토 실행 단위
-- ------------------------------------------------------------
CREATE TABLE document_review (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_pr_ref        UUID,                             -- BE doc_pr.id 참조 (수동 검토는 NULL 가능)
    document_ref      UUID NOT NULL,                    -- BE document.id 참조
    trigger_type      VARCHAR(10) NOT NULL
                        CHECK (trigger_type IN ('manual', 'auto')),
    overall_verdict   VARCHAR(20) NOT NULL
                        CHECK (overall_verdict IN ('approve', 'reject_recommended')),
    requested_by_ref  UUID NOT NULL,                    -- BE user.id 참조
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_document_review_doc_pr ON document_review (doc_pr_ref);
CREATE INDEX idx_document_review_document ON document_review (document_ref);

-- ------------------------------------------------------------
-- 3. DocumentLion — 검토 결과 항목 (심각도별)
-- ------------------------------------------------------------
CREATE TABLE document_review_issue (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id             UUID NOT NULL REFERENCES document_review (id) ON DELETE CASCADE,
    severity              VARCHAR(10) NOT NULL
                            CHECK (severity IN ('critical', 'medium', 'minor')),
    issue_type            VARCHAR(20) NOT NULL
                            CHECK (issue_type IN ('conflict', 'inconsistency', 'charter_violation')),
    description            TEXT NOT NULL,
    related_document_ref  UUID,                         -- 충돌 대상 연결 문서(BE document.id)
    charter_rule_id        UUID REFERENCES charter_rule (id) ON DELETE SET NULL,  -- charter_violation일 때만 값
    location_ref           TEXT,                         -- 문장/섹션 위치 식별자 (에디터가 정의하는 형식)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_review_issue_review ON document_review_issue (review_id);
CREATE INDEX idx_review_issue_severity ON document_review_issue (review_id, severity);

-- ------------------------------------------------------------
-- 4. Dev-aware Translation — 번역 캐시 (선택: on-demand만 갈 경우 생략 가능)
-- ------------------------------------------------------------
CREATE TABLE translation_cache (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_ref        UUID NOT NULL,                  -- BE document.id 참조
    source_lang         VARCHAR(10) NOT NULL,
    target_lang         VARCHAR(10) NOT NULL,
    translated_content   TEXT NOT NULL,
    preserved_terms      TEXT[],                         -- 원문 그대로 유지된 용어 목록
    source_content_hash  VARCHAR(64) NOT NULL,            -- 원문 변경 감지용 (재번역 필요 판단)
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_ref, target_lang)
);

-- ------------------------------------------------------------
-- 5. AI Writing Assistant — 제안 로그 (선택: 통계/성공기준용, 없어도 기능 동작엔 지장 없음)
-- ------------------------------------------------------------
CREATE TABLE writing_suggestion_log (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_ref       UUID NOT NULL,                   -- BE document.id 참조
    requested_by_ref   UUID NOT NULL,                   -- BE user.id 참조
    suggestion_type    VARCHAR(20) NOT NULL
                        CHECK (suggestion_type IN ('structure', 'next-paragraph', 'clarity')),
    suggestion_text    TEXT NOT NULL,
    accepted           BOOLEAN,                         -- NULL = 아직 반응 없음
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_writing_suggestion_document ON writing_suggestion_log (document_ref);
