from fastapi import APIRouter
from app.api.v1.endpoints import events, spots, public, webhooks

api_router = APIRouter()
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(spots.router, prefix="/events", tags=["spots"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


