# Backward-compatibility shim — real implementation lives in infrastructure/persistence.
# All existing imports from app.services.historical_zone_scheduler continue to work unchanged.
from app.infrastructure.persistence.historical_zone_scheduler import (  # noqa: F401
    ENABLE_HISTORICAL_ZONE_DAILY,
    HISTORICAL_ZONE_OUTPUT_DIR,
    get_historical_zone_scheduler_status,
    run_historical_zone_daily_if_due,
)
