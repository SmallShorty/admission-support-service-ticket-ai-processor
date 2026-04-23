import logging
import warnings
from fastapi import FastAPI
from src.api.routes import routers
from src.api.middleware import setup_cors
from src.core.config import settings
from src.core.queues import classification_queue

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_main")


def create_app() -> FastAPI:
    """
    FastAPI application factory.
    """
    app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

    # Apply CORS policy from our separate middleware file
    setup_cors(app)

    # Include routers
    for router, tag in routers:
        app.include_router(router, prefix=settings.API_V1_STR, tags=[tag])
        logger.info(f"Mounted router: {tag}")

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "active", "service": settings.PROJECT_NAME}

    return app


app = create_app()


@app.on_event("startup")
async def on_startup():
    await classification_queue.start()
    logger.info("Application startup sequence completed.")


@app.on_event("shutdown")
async def on_shutdown():
    await classification_queue.stop()
    logger.info("Application shutdown sequence completed.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["src"],  # Отслеживаем только src
        reload_excludes=[".venv", "__pycache__", "*.pyc", "logs", "data", "models"],
        log_level="info",
        access_log=False,  # Отключаем access логи для скорости
        use_colors=True,
    )
