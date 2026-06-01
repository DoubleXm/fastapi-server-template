from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.todos.router import router as todos_router
from app.api.v1.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(todos_router)
