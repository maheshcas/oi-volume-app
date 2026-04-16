# Backward-compatibility shim — real implementation lives in infrastructure/persistence.
# All existing imports from app.services.daily_context continue to work unchanged.
from app.infrastructure.persistence.daily_context import (  # noqa: F401
    get_daily_context,
    SYMBOL_TO_INDEX_NAMES,
    LOOKBACK_DAYS,
    DAILY_CONTEXT_DIR,
)
