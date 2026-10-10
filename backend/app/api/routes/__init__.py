from fastapi import APIRouter

from app.api.routes import files, health, system

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(files.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
