"""테스트 전역 DB 격리.

kb_runner.py/refund_runner.py/nodes.py는 실제 개발용 SQLite(backend/agentops.db)를
직접 열어 쓴다(app.db.session.async_session_factory, LangGraph 체크포인터는
agents/refund_agent/checkpointer.get_sqlite_checkpoint_path()). 이 fixture가
없으면 pytest를 돌릴 때마다 dev DB에 테스트 문서/케이스/체크포인트가 그대로
쌓여, 실제 지식베이스 관리 대시보드 같은 화면에 테스트 데이터가 노출된다
(GitHub 이슈 #1).

호출부가 전부 `db_session.async_session_factory()`/`checkpointer_module.
get_sqlite_checkpoint_path()`처럼 모듈 속성으로 접근하도록 되어 있어(이름을
직접 import하면 여기서 monkeypatch해도 이미 바인딩된 참조라 반영되지 않는다),
아래에서 그 모듈 속성만 바꿔치기하면 백그라운드 태스크까지 전부 격리된
임시 SQLite 파일을 쓰게 된다.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.refund_agent import checkpointer as checkpointer_module
from app.api.deps import require_admin_auth
from app.core.config import get_settings
from app.db import models  # noqa: F401 — Base.metadata에 테이블을 등록시키기 위한 임포트
from app.db import session as db_session
from app.main import app


@pytest.fixture(autouse=True)
async def isolated_test_db(monkeypatch: pytest.MonkeyPatch):
    # Phase 6.2: 관리자 라우터는 HTTP Basic 인증이 걸려 있다. 통합 테스트는
    # 인증 로직 자체가 아니라 그 뒤의 비즈니스 로직을 검증하는 게 목적이므로
    # 기본적으로 우회한다 — 인증 자체는 tests/test_admin_auth.py에서 별도 검증.
    app.dependency_overrides[require_admin_auth] = lambda: None

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with test_engine.begin() as conn:
            await conn.run_sync(db_session.Base.metadata.create_all)
        test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        monkeypatch.setattr(db_session, "engine", test_engine)
        monkeypatch.setattr(db_session, "async_session_factory", test_session_factory)
        # LangGraph AsyncSqliteSaver 체크포인터도 같은 임시 파일을 공유한다 —
        # 운영 코드(checkpointer.py)가 "메인 DB와 같은 SQLite 파일을 쓴다"고
        # 명시한 것과 동일한 구조를 테스트에서도 유지한다.
        monkeypatch.setattr(checkpointer_module, "get_sqlite_checkpoint_path", lambda: str(db_path))

        # 업로드 라우트(지식베이스 PDF, 환불 증빙 이미지)는 get_settings()가
        # 매번 반환하는 캐시된 Settings 인스턴스의 경로를 그때그때 읽으므로,
        # 그 인스턴스 자체를 바꿔치기하면 실제 backend/data/ 아래에 테스트
        # 파일이 쌓이지 않는다.
        settings = get_settings()
        monkeypatch.setattr(settings, "policy_docs_dir", str(Path(tmpdir) / "policy_docs"))
        monkeypatch.setattr(settings, "upload_dir", str(Path(tmpdir) / "uploads"))

        try:
            yield
        finally:
            await test_engine.dispose()
            app.dependency_overrides.pop(require_admin_auth, None)
