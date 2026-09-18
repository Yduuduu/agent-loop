from app.core.config import get_settings


def get_langfuse_callback():
    """Langfuse 키가 설정된 경우에만 LangChain 콜백 핸들러를 반환한다.

    langfuse v4는 전역 싱글턴 클라이언트를 통해 인증 정보를 읽으므로,
    pydantic-settings가 .env에서 읽은 값을 os.environ이 아니라 여기서
    명시적으로 Langfuse() 생성자에 넘겨 초기화한다.
    """
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None

    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return CallbackHandler()
