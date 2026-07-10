"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from dealeriq_api.core.config import get_settings
from dealeriq_api.core.errors import register_error_handlers
from dealeriq_api.core.limiter import limiter
from dealeriq_api.core.logging import RequestLoggingMiddleware, configure_logging
from dealeriq_api.routes import (
    audit_log,
    auth,
    branches,
    customers,
    forecasts,
    jobs,
    leads,
    orders,
    permissions,
    roles,
    users,
    vehicle_models,
    vehicle_units,
)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="DealerIQ API",
        version="0.1.0",
        description="Dealership intelligence platform — REST API (DIQ-SRS-001).",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
    )

    app.state.limiter = limiter
    # slowapi's handler type doesn't perfectly match Starlette's exception-handler stub —
    # known friction point, not a real type mismatch.
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    register_error_handlers(app)

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(roles.router)
    app.include_router(permissions.router)
    app.include_router(audit_log.router)
    app.include_router(branches.router)
    app.include_router(vehicle_models.router)
    app.include_router(vehicle_units.router)
    app.include_router(customers.router)
    app.include_router(leads.router)
    app.include_router(orders.router)
    app.include_router(jobs.router)
    app.include_router(forecasts.router)

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
