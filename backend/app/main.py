import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.auth import SupabaseAuthMiddleware
from app.core.cache import cache
from app.dependencies import get_current_user
from app.routers import option_chain
from app.services.background_updater import background_update_loop
from app.services.stability_logger import StabilityLoggerService

logger = logging.getLogger("optionlens.main")

_stability_logger = StabilityLoggerService()

# ---------------------------------------------------------------------------
# Allowed CORS origins — set ALLOWED_ORIGINS env var to a comma-separated list
# of frontend URLs (e.g. "https://your-app.netlify.app,http://localhost:5173").
# Never use wildcard ("*") together with allow_credentials=True.
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    updater_stop = asyncio.Event()
    updater_task = asyncio.create_task(background_update_loop(updater_stop))
    logger.info("Background updater task started")

    stability_stop: asyncio.Event | None = None
    stability_task: asyncio.Task | None = None
    if _stability_logger.enabled:
        stability_stop = asyncio.Event()
        stability_task = asyncio.create_task(_stability_logger.run(stability_stop))
        logger.info("Stability logger task started")
    else:
        logger.info("Stability logger disabled by configuration")

    yield

    # ---- shutdown ----
    updater_stop.set()
    try:
        await asyncio.wait_for(updater_task, timeout=10)
        logger.info("Background updater task stopped")
    except TimeoutError:
        updater_task.cancel()
        logger.warning("Background updater task timed out on shutdown — cancelled")

    if stability_task and stability_stop:
        stability_stop.set()
        try:
            await asyncio.wait_for(stability_task, timeout=10)
            logger.info("Stability logger task stopped")
        except TimeoutError:
            stability_task.cancel()
            logger.warning("Stability logger task timed out on shutdown — cancelled")


app = FastAPI(title="NSE OI-Volume App", version="1.0", lifespan=lifespan)
app.include_router(option_chain.router, prefix="/api")
app.add_middleware(SupabaseAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")



@app.get("/")
def root():
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path)


@app.get("/health")
async def health():
    state = await cache.get_cached_data()
    return {
        "status": "ok" if state.get("summary_data") else "initializing",
        "last_update": state.get("last_update").isoformat() if state.get("last_update") else None,
        "stale_data": state.get("stale_data", True),
    }


@app.get("/api/analysis")
def protected_analysis(current_user: dict = Depends(get_current_user)):
    """
    Protected example endpoint.
    Frontend should pass Supabase access token as Authorization: Bearer <token>.
    """
    return {
        "status": "ok",
        "user": current_user,
        "analysis": {
            "message": "Authenticated request accepted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

# Only run Uvicorn if this script is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
