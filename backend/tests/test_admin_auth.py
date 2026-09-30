"""Phase 6.2: 관리자 라우터(환불 케이스, 지식베이스) 앞단 HTTP Basic 인증 검증.

conftest.py의 isolated_test_db가 기본적으로 require_admin_auth를 우회하므로,
이 파일은 그 우회를 해제하고 인증 로직 자체만 검증한다.
"""

import base64

import httpx
import pytest

from app.api.deps import require_admin_auth
from app.core.config import get_settings
from app.main import app


def _basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture(autouse=True)
def enable_real_auth():
    # isolated_test_db가 기본으로 걸어둔 우회를 이 파일에서만 해제한다.
    app.dependency_overrides.pop(require_admin_auth, None)
    yield
    app.dependency_overrides[require_admin_auth] = lambda: None


@pytest.fixture
def configured_credentials(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    return "admin", "s3cret"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def test_kb_documents_requires_auth(client: httpx.AsyncClient, configured_credentials):
    resp = await client.get("/api/knowledge-base/documents")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"


async def test_kb_documents_rejects_wrong_credentials(
    client: httpx.AsyncClient, configured_credentials
):
    resp = await client.get(
        "/api/knowledge-base/documents", headers=_basic_auth_header("admin", "wrong")
    )
    assert resp.status_code == 401


async def test_kb_documents_accepts_correct_credentials(
    client: httpx.AsyncClient, configured_credentials
):
    username, password = configured_credentials
    resp = await client.get(
        "/api/knowledge-base/documents", headers=_basic_auth_header(username, password)
    )
    assert resp.status_code == 200


async def test_refund_requests_requires_auth(client: httpx.AsyncClient, configured_credentials):
    resp = await client.get("/api/refund-requests")
    assert resp.status_code == 401


async def test_missing_admin_credentials_config_fails_closed(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    # .env에 로컬 개발용 자격증명이 실제로 설정돼 있을 수 있으므로, 이 테스트는
    # "미설정" 상태를 명시적으로 만들어 환경에 좌우되지 않게 한다.
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_username", "")
    monkeypatch.setattr(settings, "admin_password", "")

    resp = await client.get(
        "/api/knowledge-base/documents", headers=_basic_auth_header("anyone", "anything")
    )
    assert resp.status_code == 500


async def test_health_does_not_require_auth(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200


CSRF_HEADER = {"X-Requested-With": "XMLHttpRequest"}


async def test_mutating_request_without_csrf_header_is_rejected(
    client: httpx.AsyncClient, configured_credentials
):
    username, password = configured_credentials
    # 일반 <form> 제출을 흉내낸다: 유효한(브라우저가 자동 재첨부했을) Basic
    # Auth는 있지만, 커스텀 헤더는 HTML form으로 붙일 수 없다.
    resp = await client.delete(
        "/api/knowledge-base/documents/does-not-exist",
        headers=_basic_auth_header(username, password),
    )
    assert resp.status_code == 403


async def test_mutating_request_with_csrf_header_reaches_route_handler(
    client: httpx.AsyncClient, configured_credentials
):
    username, password = configured_credentials
    resp = await client.delete(
        "/api/knowledge-base/documents/does-not-exist",
        headers={**_basic_auth_header(username, password), **CSRF_HEADER},
    )
    # CSRF 검사를 통과해 라우트 핸들러까지 도달했다는 뜻(존재하지 않는 문서라 404).
    assert resp.status_code == 404


async def test_get_request_does_not_require_csrf_header(
    client: httpx.AsyncClient, configured_credentials
):
    username, password = configured_credentials
    resp = await client.get(
        "/api/knowledge-base/documents", headers=_basic_auth_header(username, password)
    )
    assert resp.status_code == 200
