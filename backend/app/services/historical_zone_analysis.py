# Backward-compatibility shim — real implementation lives in infrastructure/persistence.
# All existing imports from app.services.historical_zone_analysis continue to work unchanged.
from app.infrastructure.persistence.historical_zone_analysis import main  # noqa: F401
