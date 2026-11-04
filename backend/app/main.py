from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import admin, public
from app.api.deps import ApiError, get_state
from app.body_limit import BodyLimitMiddleware, BodyTooLarge
from app.config import Settings, enforce_single_worker
from app.core.cache import ResultCache
from app.core.local_engine import LocalEngine
from app.core.quota import QuotaManager
from app.core.registry import AccountRegistry
from app.core.scheduler import Scheduler
from app.db import make_engine, make_session_factory
from app.logging_setup import configure_logging
from app.models import Account
from app.panel import register_panel
from app.providers.baidu import BaiduAdapter
from app.providers.base import ProviderAdapter
from app.providers.tencent import TencentAdapter
from app.runtime_settings import load_runtime_settings
from app.security_headers import SecurityHeadersMiddleware
from app.state import AppState

logger = logging.getLogger(__name__)


async def _quota_flush_loop(state: AppState) -> None:
    while True:
        await asyncio.sleep(2.0)
        try:
            async with state.session_factory() as session:
                await state.quota.flush(session)
        except asyncio.CancelledError:  # pragma: no cover - loop shutdown
            raise
        except Exception:  # noqa: BLE001 - keep the flush loop alive
            logger.exception("quota flush failed")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()  # type: ignore[call-arg]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(resolved.log_level)
        enforce_single_worker()
        resolved.data_path.mkdir(parents=True, exist_ok=True)

        engine = make_engine(resolved.database_url)
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            accounts = (await session.execute(select(Account))).scalars().all()
            runtime = await load_runtime_settings(session, resolved)

        registry = AccountRegistry(resolved.master_key_bytes)
        registry.load(list(accounts))
        quota = QuotaManager()
        async with session_factory() as session:
            await quota.load(session, registry.all())

        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=8.0, write=8.0, pool=3.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=False,
            trust_env=False,
        )
        adapters: dict[str, ProviderAdapter] = {
            "baidu": BaiduAdapter(http_client),
            "tencent": TencentAdapter(http_client),
        }
        local_engine = LocalEngine(
            enabled=runtime.local_ocr_enabled,
            max_concurrency=resolved.local_ocr_max_concurrency,
            timeout_ms=resolved.local_ocr_timeout_ms,
            reserve_ms=resolved.local_ocr_reserve_ms,
            min_budget_ms=resolved.local_ocr_min_budget_ms,
        )
        state = AppState(
            settings=resolved,
            runtime=runtime,
            engine=engine,
            session_factory=session_factory,
            registry=registry,
            quota=quota,
            cache=ResultCache(
                runtime.cache_enabled,
                runtime.cache_max_entries,
                runtime.cache_ttl_seconds,
            ),
            http=http_client,
            adapters=adapters,
            scheduler=Scheduler(
                registry,
                quota,
                adapters,
                local_engine=local_engine,
                reserve_ms=resolved.local_ocr_reserve_ms,
                min_budget_ms=resolved.local_ocr_min_budget_ms,
            ),
            local_engine=local_engine,
            semaphore=asyncio.Semaphore(resolved.max_concurrent_requests),
            frontend_built=panel_available,
        )
        app.state.gw = state
        await state.local_engine.start()
        flush_task = asyncio.create_task(_quota_flush_loop(state))
        try:
            yield
        finally:
            flush_task.cancel()
            await asyncio.gather(flush_task, return_exceptions=True)
            await state.local_engine.shutdown()
            try:
                async with session_factory() as session:
                    await quota.flush(session)
            except Exception:  # noqa: BLE001 - best-effort final flush
                logger.exception("final quota flush failed")
            await http_client.aclose()
            await engine.dispose()

    app = FastAPI(title="OCR Gateway", version=__version__, lifespan=lifespan)
    app.state.settings = resolved

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = str(uuid.uuid4())
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "request",
            extra={
                "extra_fields": {
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                }
            },
        )
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        error: dict[str, object] = {"code": exc.code, "message": exc.message}
        if exc.fields:
            error["fields"] = exc.fields
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "request_id": getattr(request.state, "request_id", ""),
                "error": error,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            400: "BAD_REQUEST",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }.get(exc.status_code, "HTTP_ERROR")
        message = {
            400: "invalid request",
            404: "not found",
            405: "method not allowed",
        }.get(exc.status_code, str(exc.detail))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "request_id": getattr(request.state, "request_id", ""),
                "error": {"code": code, "message": message},
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(BodyTooLarge)
    async def body_too_large_handler(request: Request, exc: BodyTooLarge) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "request_id": getattr(request.state, "request_id", ""),
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "request body exceeds the size limit",
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "request_id": getattr(request.state, "request_id", ""),
                "error": {"code": "BAD_REQUEST", "message": "invalid request"},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={
                "request_id": getattr(request.state, "request_id", ""),
                "error": {"code": "INTERNAL_ERROR", "message": "internal error"},
            },
        )

    @app.get("/healthz")
    async def healthz(state: AppState = Depends(get_state)) -> JSONResponse:
        try:
            async with state.session_factory() as session:
                await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=1.0)
        except Exception:  # noqa: BLE001 - health check must not raise
            return JSONResponse(
                status_code=503,
                content={"status": "error", "db": "error", "version": __version__},
            )
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "db": "ok", "version": __version__},
        )

    app.include_router(public.router)
    app.include_router(admin.router)
    # The panel catch-all must come after every API route so it only sees leftovers.
    panel_available = register_panel(app, resolved.frontend_dist_path)
    # T1: stream-count every request body; covers chunked bodies without Content-Length.
    app.add_middleware(
        BodyLimitMiddleware, max_bytes=resolved.max_upload_bytes * 2
    )
    # Added last => outermost, so even limit/error responses carry the headers (D-A4).
    app.add_middleware(SecurityHeadersMiddleware)
    return app


app = create_app()
