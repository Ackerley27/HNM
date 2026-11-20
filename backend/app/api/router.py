from fastapi import APIRouter

from app.api.routes import alerts, auth, dashboard, departments, devices, reports, traffic

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(traffic.router)
api_router.include_router(alerts.router)
api_router.include_router(devices.router)
api_router.include_router(departments.router)
api_router.include_router(reports.router)
