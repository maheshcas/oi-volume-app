# Backward-compatibility shim — real implementation lives in infrastructure/feeds.
# All existing imports from app.services.nse_client continue to work unchanged.
from app.infrastructure.feeds.nse_client import (  # noqa: F401
    fetch_index_data,
    fetch_index_history,
    fetch_option_chain,
    fetch_option_chain_contract_info,
)
