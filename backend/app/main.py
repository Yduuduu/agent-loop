from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.knowledge_base import router as knowledge_base_router
from app.api.routes.refund import router as refund_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(refund_router)
    app.include_router(knowledge_base_router)

    return app


app = create_app()
