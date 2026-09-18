"""LangGraph 체크포인터 저장 위치.

roadmap: "기존 DB와 동일 저장소 활용 권장" — 메인 SQLAlchemy DB와 같은 SQLite
파일을 공유한다(체크포인터는 자체 테이블 네임스페이스를 쓰므로 충돌 없음).
"""

from app.core.config import get_settings

_SQLITE_PREFIX = "sqlite+aiosqlite:///"


def get_sqlite_checkpoint_path() -> str:
    settings = get_settings()
    if not settings.database_url.startswith(_SQLITE_PREFIX):
        raise ValueError(
            "AsyncSqliteSaver 체크포인터는 현재 sqlite+aiosqlite database_url만 지원한다: "
            f"{settings.database_url}"
        )
    return settings.database_url.removeprefix(_SQLITE_PREFIX)
