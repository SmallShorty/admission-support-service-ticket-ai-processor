from .classification import router as classification_router
from .priority import router as priority_router
from .process import router as process_router

routers = [
    (classification_router, "Classification"),
    (priority_router, "Priority"),
    (process_router, "Process"),
]

__all__ = ["routers"]
