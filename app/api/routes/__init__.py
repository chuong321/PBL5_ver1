"""API routes."""

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.stats import router as stats_router
from app.api.routes.esp32_ws import router as esp32_router

__all__ = ["dashboard_router", "stats_router", "esp32_router"]
