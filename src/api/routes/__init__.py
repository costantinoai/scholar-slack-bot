"""API route modules."""

from .authors import router as authors_router
from .publications import router as publications_router
from .plugins import router as plugins_router

__all__ = [
    "authors_router",
    "publications_router",
    "plugins_router",
]
