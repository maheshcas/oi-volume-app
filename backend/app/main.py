import os
import asyncio
import logging
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

app = FastAPI(title="NSE OI-Volume App", version="1.0")
app.include_router(option_chain.router, prefix="/api")
app.add_middleware(SupabaseAuthMiddleware)

_updater_stop_event: asyncio.Event | None = None
_updater_task: asyncio.Task | None = None
_stability_stop_event: asyncio.Event | None = None
_stability_task: asyncio.Task | None = None
_stability_logger = StabilityLoggerService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
            "timestamp": os.times().elapsed,
        },
    }


@app.on_event("startup")
async def on_startup() -> None:
    global _updater_stop_event, _updater_task, _stability_stop_event, _stability_task
    if _updater_task and not _updater_task.done():
        logger.info("Background updater already running")
    else:
        _updater_stop_event = asyncio.Event()
        _updater_task = asyncio.create_task(background_update_loop(_updater_stop_event))
        logger.info("Background updater task started")
    if _stability_logger.enabled:
        if _stability_task and not _stability_task.done():
            logger.info("Stability logger already running")
        else:
            _stability_stop_event = asyncio.Event()
            _stability_task = asyncio.create_task(_stability_logger.run(_stability_stop_event))
            logger.info("Stability logger task started")
    else:
        logger.info("Stability logger disabled")



@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _updater_stop_event, _updater_task, _stability_stop_event, _stability_task
    if _updater_stop_event:
        _updater_stop_event.set()
    if _updater_task:
        try:
            await asyncio.wait_for(_updater_task, timeout=10)
        except TimeoutError:
            _updater_task.cancel()
    if _stability_stop_event:
        _stability_stop_event.set()
    if _stability_task:
        try:
            await asyncio.wait_for(_stability_task, timeout=10)
        except TimeoutError:
            _stability_task.cancel()
    _updater_task = None
    _updater_stop_event = None
    _stability_task = None
    _stability_stop_event = None
    logger.info("Background updater task stopped")

# Only run Uvicorn if this script is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
