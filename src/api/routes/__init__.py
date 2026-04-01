from .classification import router as classification_router
from .priority import router as priority_router

routers = [
    (classification_router, "Classification"),
    (priority_router, "Priority"),
]

__all__ = ["routers"]
