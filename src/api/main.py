import logging
import warnings
from fastapi import FastAPI
from src.api.routes import classification
from src.api.middleware import setup_cors
from src.core.config import settings

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
    app.include_router(
        classification.router, prefix=settings.API_V1_STR, tags=["Classification"]
    )

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "active", "service": settings.PROJECT_NAME}

    return app


app = create_app()


@app.on_event("startup")
async def on_startup():
    logger.info("Application startup sequence completed.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)
