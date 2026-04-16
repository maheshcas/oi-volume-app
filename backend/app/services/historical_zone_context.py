# Backward-compatibility shim — real implementation lives in infrastructure/persistence.
# All existing imports from app.services.historical_zone_context continue to work unchanged.
from app.infrastructure.persistence.historical_zone_context import (  # noqa: F401
    HISTORICAL_ZONE_DIR,
    build_historical_zone_context_from_payload,
    get_cached_historical_zone_context,
    load_latest_historical_zone_context,
    set_cached_historical_zone_context,
)
