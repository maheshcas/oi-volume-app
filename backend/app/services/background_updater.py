# Backward-compatibility shim — real implementation lives in application/use_cases.
# Tests and any remaining callers that import from app.services.background_updater
# continue to work unchanged.
from app.application.use_cases.background_updater import (  # noqa: F401
    background_update_loop,
    run_update_cycle,
    _canonicalize_trap_reference,
)
