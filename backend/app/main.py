from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.rate_limit import limiter
from app.routers import (
    admin_auth,
    admin_booking,
    admin_content,
    admin_leads,
    admin_settings,
    admin_stats,
    admin_uploads,
    public_booking,
    public_chat,
    public_config,
    public_content,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Perennia API",
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    if settings.allowed_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return resp

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Never leak stack traces / internals to the client — log server
        # side (Pass 10 wires structured logging), return a flat 500.
        import logging
        logging.getLogger("perennia").exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(admin_auth.router)
    app.include_router(admin_settings.router)
    app.include_router(admin_content.router)
    app.include_router(admin_uploads.router)
    app.include_router(admin_booking.router)
    app.include_router(admin_leads.router)
    app.include_router(admin_stats.router)
    app.include_router(public_config.router)
    app.include_router(public_content.router)
    app.include_router(public_booking.router)
    app.include_router(public_chat.router)

    app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
