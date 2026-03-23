import logging
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings

logger = logging.getLogger("api.middleware")


def setup_cors(app):
    """
    Configures Cross-Origin Resource Sharing (CORS) for the application.
    Allows frontend applications to interact with the API.
    """
    logger.info("Configuring CORS policy...")

    # Origins that are allowed to make cross-site HTTP requests
    origins = [
        str(origin).strip().rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info(f"CORS initialized with origins: {origins}")
