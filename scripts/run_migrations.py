"""scripts/migrations/*.sql를 순서대로 적용한다.

이 프로젝트는 Alembic을 도입하지 않는다(설계 7절). 대신 이 러너가 두 가지를 보장한다.

1. **파일명 순으로 적용한다.** 나중 마이그레이션이 앞선 것에 의존할 수 있다.
2. **적용한 파일명을 schema_migrations에 기록한다.** 지금 SQL은 IF NOT EXISTS라 여러 번
   돌려도 되지만, 앞으로의 마이그레이션이 UPDATE나 INSERT면 두 번 돌면 망가진다.

배포 파이프라인이 새 api 컨테이너를 띄우기 전에 이걸 실행한다. 순서를 뒤집으면 새 코드가
낡은 스키마로 트래픽을 받는 구간이 생긴다.
"""

import logging
import sys
import time
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_migrations")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_TRACKING_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename VARCHAR(255) NOT NULL PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def applied_migrations(conn: Connection) -> set[str]:
    return set(conn.execute(text("SELECT filename FROM schema_migrations")).scalars().all())


def pending_files(migrations_dir: Path, applied: set[str]) -> list[Path]:
    if not migrations_dir.is_dir():
        return []
    return [p for p in sorted(migrations_dir.glob("*.sql")) if p.name not in applied]


def statements(sql: str) -> list[str]:
    """SQL 파일을 실행 가능한 문장 목록으로 쪼갠다.

    psycopg는 파라미터 없는 execute에서도 여러 문장을 한 번에 받아주지 않는 경우가 있어
    직접 분리한다. 줄 단위 주석(--)을 먼저 걷어낸다.

    문자열 리터럴 안의 세미콜론까지 처리하지는 않는다. 이 프로젝트의 마이그레이션은 DDL
    위주이고, 필요해지면 그 문장만 파일 하나로 분리하면 된다.
    """
    without_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [s.strip() for s in without_comments.split(";") if s.strip()]


def run_migrations(engine: Engine, migrations_dir: Path | None = None) -> list[str]:
    """적용되지 않은 마이그레이션을 실행하고 적용한 파일명 목록을 돌려준다."""
    migrations_dir = MIGRATIONS_DIR if migrations_dir is None else migrations_dir

    with engine.begin() as conn:
        conn.execute(text(_TRACKING_DDL))

    with engine.connect() as conn:
        already = applied_migrations(conn)

    targets = pending_files(migrations_dir, already)
    if not targets:
        logger.info("적용할 마이그레이션이 없다 (기록된 것 %d개)", len(already))
        return []

    applied: list[str] = []
    for path in targets:
        logger.info("적용: %s", path.name)
        # 파일 하나가 한 트랜잭션이다. 실패하면 그 파일의 변경은 롤백되고 기록도 남지 않는다 —
        # 실패한 것을 적용됨으로 기록하면 영구히 건너뛴다.
        with engine.begin() as conn:
            for stmt in statements(path.read_text()):
                conn.execute(text(stmt))
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"), {"f": path.name}
            )
        applied.append(path.name)

    logger.info("완료 — %d개 적용", len(applied))
    return applied


def wait_for_db(engine: Engine, attempts: int = 30, delay: float = 1.0) -> None:
    """DB 컨테이너가 아직 기동 중일 수 있다 — 접속될 때까지 재시도한다."""
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == attempts:
                raise
            logger.info("DB 접속 대기 중 (%d/%d)", attempt, attempts)
            time.sleep(delay)


def main() -> int:
    from app.core.config import settings

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    wait_for_db(engine)
    run_migrations(engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
