from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.analytics import store
from app.api.router import router
from app.core.config import settings

logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stryk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ds = store.get()
        log.info("dataset ready: %s matches", len(ds.matches))
    except Exception as exc:  # the API still boots so /health can explain itself
        log.error("could not load dataset at startup: %s", exc)
    yield


app = FastAPI(
    title="Stryk API",
    description="Cricket intelligence over Cricsheet ball-by-ball data.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):  # pragma: no cover
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal error computing this analysis.", "path": request.url.path},
    )


@app.get("/health", tags=["admin"])
def health():
    try:
        ds = store.get()
        return {
            "status": "ok" if not ds.matches.empty else "empty",
            "deliveries": int(store.ball_totals()["balls"].sum()),
            "matches": int(ds.matches["id"].nunique()) if not ds.matches.empty else 0,
            "loaded_at": ds.loaded_at.isoformat() + "Z",
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
