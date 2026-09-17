from fastapi import APIRouter
from app.api.v1.endpoints import events, spots, public, webhooks, orders, reminders, broadcast, auth, admin_users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(spots.router, prefix="/events", tags=["spots"])
api_router.include_router(orders.router, prefix="/events", tags=["orders"])
api_router.include_router(reminders.router, prefix="/events", tags=["reminders"])
api_router.include_router(reminders.system_router, prefix="/system", tags=["system"])
api_router.include_router(broadcast.router, prefix="/events", tags=["broadcast"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


