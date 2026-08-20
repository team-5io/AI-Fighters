"""마이그레이션 러너.

Alembic을 도입하지 않는다(설계 7절). 대신 scripts/migrations/*.sql을 파일명 순으로
적용하고, 적용한 파일명을 schema_migrations에 기록해 두 번 실행되지 않게 한다.

기록을 두는 이유: 지금 SQL은 IF NOT EXISTS라 여러 번 돌려도 되지만, 앞으로의
마이그레이션이 UPDATE나 INSERT면 두 번 돌면 망가진다.
"""

import pytest
from sqlalchemy import create_engine, text

from scripts.run_migrations import applied_migrations, pending_files, run_migrations


@pytest.fixture
def engine():
    # 러너 자체는 DB 종류에 의존하지 않는다 — schema_migrations DDL을 표준 SQL로 썼다
    return create_engine("sqlite://")


@pytest.fixture
def migrations_dir(tmp_path):
    d = tmp_path / "migrations"
    d.mkdir()
    return d


def _write(d, name, sql):
    (d / name).write_text(sql)


class TestRunMigrations:
    def test_empty_directory_is_a_noop(self, engine, migrations_dir):
        assert run_migrations(engine, migrations_dir) == []

    def test_creates_tracking_table(self, engine, migrations_dir):
        run_migrations(engine, migrations_dir)

        with engine.connect() as c:
            assert applied_migrations(c) == set()

    def test_applies_pending_file(self, engine, migrations_dir):
        _write(migrations_dir, "2026-01-01_a.sql", "CREATE TABLE thing (id INTEGER)")

        applied = run_migrations(engine, migrations_dir)

        assert applied == ["2026-01-01_a.sql"]
        with engine.connect() as c:
            c.execute(text("SELECT id FROM thing"))

    def test_applies_in_filename_order(self, engine, migrations_dir):
        _write(migrations_dir, "2026-01-02_b.sql", "INSERT INTO log (n) VALUES (2)")
        _write(migrations_dir, "2026-01-01_a.sql", "CREATE TABLE log (n INTEGER)")

        applied = run_migrations(engine, migrations_dir)

        # 순서가 뒤바뀌면 두 번째 파일이 없는 테이블에 INSERT하다 실패한다
        assert applied == ["2026-01-01_a.sql", "2026-01-02_b.sql"]

    def test_second_run_applies_nothing(self, engine, migrations_dir):
        _write(migrations_dir, "2026-01-01_a.sql", "CREATE TABLE thing (id INTEGER)")
        run_migrations(engine, migrations_dir)

        assert run_migrations(engine, migrations_dir) == []

    def test_non_idempotent_sql_is_not_reapplied(self, engine, migrations_dir):
        """기록이 하는 일 — 두 번 돌면 값이 두 배가 되는 SQL을 막는다."""
        _write(migrations_dir, "2026-01-01_a.sql", "CREATE TABLE c (n INTEGER)")
        _write(migrations_dir, "2026-01-02_b.sql", "INSERT INTO c (n) VALUES (1)")
        run_migrations(engine, migrations_dir)
        run_migrations(engine, migrations_dir)

        with engine.connect() as c:
            assert c.execute(text("SELECT COUNT(*) FROM c")).scalar() == 1

    def test_only_new_file_is_applied_on_later_run(self, engine, migrations_dir):
        _write(migrations_dir, "2026-01-01_a.sql", "CREATE TABLE a (id INTEGER)")
        run_migrations(engine, migrations_dir)
        _write(migrations_dir, "2026-01-02_b.sql", "CREATE TABLE b (id INTEGER)")

        assert run_migrations(engine, migrations_dir) == ["2026-01-02_b.sql"]

    def test_failure_is_not_recorded_and_raises(self, engine, migrations_dir):
        """실패한 마이그레이션을 적용된 것으로 기록하면 영구히 건너뛴다."""
        _write(migrations_dir, "2026-01-01_bad.sql", "THIS IS NOT SQL")

        with pytest.raises(Exception):
            run_migrations(engine, migrations_dir)

        with engine.connect() as c:
            assert applied_migrations(c) == set()

    def test_failure_stops_later_files(self, engine, migrations_dir):
        _write(migrations_dir, "2026-01-01_bad.sql", "THIS IS NOT SQL")
        _write(migrations_dir, "2026-01-02_good.sql", "CREATE TABLE ok (id INTEGER)")

        with pytest.raises(Exception):
            run_migrations(engine, migrations_dir)

        with engine.connect() as c:
            assert applied_migrations(c) == set()

    def test_ignores_non_sql_files(self, engine, migrations_dir):
        _write(migrations_dir, "README.md", "설명 문서")

        assert run_migrations(engine, migrations_dir) == []


class TestPendingFiles:
    def test_excludes_applied(self, migrations_dir):
        _write(migrations_dir, "2026-01-01_a.sql", "")
        _write(migrations_dir, "2026-01-02_b.sql", "")

        result = pending_files(migrations_dir, {"2026-01-01_a.sql"})

        assert [p.name for p in result] == ["2026-01-02_b.sql"]

    def test_missing_directory_is_empty(self, tmp_path):
        assert pending_files(tmp_path / "nope", set()) == []


class TestRealMigrationFile:
    def test_shipped_migration_is_discovered(self):
        """실제 배포되는 마이그레이션 파일이 러너에 잡히는지 — 경로가 어긋나면 조용히 0건이 된다."""
        from scripts.run_migrations import MIGRATIONS_DIR

        names = [p.name for p in pending_files(MIGRATIONS_DIR, set())]

        assert "2026-08-21_add_source_locale.sql" in names


class TestStatements:
    def test_splits_multiple_statements(self):
        from scripts.run_migrations import statements

        assert statements("CREATE TABLE a (id INT); CREATE TABLE b (id INT);") == [
            "CREATE TABLE a (id INT)",
            "CREATE TABLE b (id INT)",
        ]

    def test_strips_line_comments(self):
        from scripts.run_migrations import statements

        assert statements("-- 설명\nSELECT 1;\n-- 또 설명\n") == ["SELECT 1"]

    def test_ignores_trailing_whitespace_and_blanks(self):
        from scripts.run_migrations import statements

        assert statements("SELECT 1;\n\n;\n  \n") == ["SELECT 1"]


class TestShippedMigrationRuns:
    def test_shipped_file_splits_into_two_statements(self):
        """실제 마이그레이션 파일은 ALTER 두 개다 — 한 문장으로 뭉치면 psycopg에서 깨질 수 있다."""
        from scripts.run_migrations import MIGRATIONS_DIR, statements

        sql = (MIGRATIONS_DIR / "2026-08-21_add_source_locale.sql").read_text()
        parsed = statements(sql)

        assert len(parsed) == 2
        assert all(s.startswith("ALTER TABLE") for s in parsed)
