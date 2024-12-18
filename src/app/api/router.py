"""API Router Module."""

from fastapi import APIRouter
from app.api.endpoints import kpi, real_time

api_router = APIRouter()
api_router.include_router(kpi.router, prefix="/kpi", tags=["kpi"])
api_router.include_router(real_time.router, prefix="/real-time", tags=["real-time"])
