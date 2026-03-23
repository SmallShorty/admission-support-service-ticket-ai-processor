import logging
from fastapi import FastAPI
from src.api.routes import classification
from src.core.config import settings

# Global logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_main")


def create_app() -> FastAPI:
    """
    Application factory to initialize FastAPI with all configurations.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Decomposed NLP microservice for ticket classification",
    )

    # Include routers from different modules
    app.include_router(
        classification.router, prefix=settings.API_V1_STR, tags=["Classification"]
    )

    @app.get("/health", tags=["System"])
    async def health_check():
        logger.info("System health check performed")
        return {"status": "healthy", "model": settings.MODEL_NAME}

    return app


app = create_app()


@app.on_event("startup")
async def on_startup():
    logger.info(f"--- {settings.PROJECT_NAME} is booting up ---")
    logger.info(f"Environment: {settings.API_V1_STR}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)
