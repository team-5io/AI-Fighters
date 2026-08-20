-- 이 프로젝트에는 Alembic이 없다. scripts/create_tables.py는 Base.metadata.create_all을
-- 호출하는데, 이것은 '없는 테이블만' 생성하고 기존 테이블에 컬럼을 추가하지 않는다.
--
-- ai_text_translation은 신규 테이블이므로 create_all로 생성된다. 반면 아래 두 컬럼은
-- create_all로 생기지 않으므로 이 SQL을 직접 실행해야 한다.
--
-- 배포 시 이 SQL 실행을 빠뜨리면 조회에서 터진다.
--
-- 기본값 'ko'로 기존 행이 정확히 백필된다 — 지금까지 생성된 텍스트는 전부 한국어다.
-- 멱등하므로 여러 번 실행해도 안전하다.

ALTER TABLE charter_rule    ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
ALTER TABLE document_review ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10) NOT NULL DEFAULT 'ko';
