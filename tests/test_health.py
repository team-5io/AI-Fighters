"""배포 헬스체크.

CD의 deploy job은 `curl -sf /health` 하나로 성공을 판정한다. 이전 구현은 상수를 돌려줘서
DB 스키마가 코드와 어긋나도 200을 냈다 — 2026-08-21에 컬럼 하나가 빠진 채로 배포가
success로 찍히면서 charter/review 엔드포인트만 500이었다. 그 장애를 잡기 위한 것이다.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

client = TestClient(app)


def _override_get_db(fake_db):
    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db


def teardown_function():
    app.dependency_overrides.clear()


def test_ok_when_schema_matches():
    _override_get_db(MagicMock())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_queries_every_table_the_app_reads():
    """컬럼 누락은 SELECT 1로 안 잡힌다 — 실제 모델을 조회해야 컬럼 목록이 검증된다."""
    db = MagicMock()
    _override_get_db(db)

    client.get("/health")

    from app.main import _SCHEMA_CHECK_MODELS

    queried = {call.args[0] for call in db.query.call_args_list}
    assert queried == set(_SCHEMA_CHECK_MODELS)
    assert len(_SCHEMA_CHECK_MODELS) >= 5


def test_503_when_column_missing():
    """UndefinedColumn이 나면 배포가 실패로 판정돼야 한다."""
    db = MagicMock()
    db.query.side_effect = Exception("column charter_rule.some_new_column does not exist")
    _override_get_db(db)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


def test_503_when_db_unreachable():
    db = MagicMock()
    db.query.return_value.limit.return_value.all.side_effect = Exception("connection refused")
    _override_get_db(db)

    response = client.get("/health")

    assert response.status_code == 503


def test_failure_is_logged():
    db = MagicMock()
    db.query.side_effect = Exception("boom")
    _override_get_db(db)

    with patch("app.main.logger") as mock_logger:
        client.get("/health")

    assert mock_logger.exception.called
