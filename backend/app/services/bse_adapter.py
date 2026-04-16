# Backward-compatibility shim — real implementation lives in infrastructure/feeds.
# All existing imports from app.services.bse_adapter continue to work unchanged.
from app.infrastructure.feeds.bse_adapter import (  # noqa: F401
    fetch_sensex_contract_info,
    fetch_sensex_contract_info_async,
    fetch_sensex_option_chain,
    fetch_sensex_option_chain_async,
)
