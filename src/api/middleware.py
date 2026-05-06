import logging
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("api.middleware")


def setup_cors(app):
    """
    Configures Cross-Origin Resource Sharing (CORS) for the application.
    Allows frontend applications to interact with the API.
    """
    logger.info("Configuring CORS policy...")

    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3005",
        "http://127.0.0.1:3005",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info(f"CORS initialized with origins: {origins}")
