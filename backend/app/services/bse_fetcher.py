# Backward-compatibility shim — real implementation lives in infrastructure/feeds.
# All existing imports from app.services.bse_fetcher continue to work unchanged.
from app.infrastructure.feeds.bse_fetcher import (  # noqa: F401
    StrikeData,
    OptionChainData,
    fetch_expiry_and_spot,
    fetch_option_chain,
    get_sensex_option_chain,
    normalise_chain,
    chain_to_sr_input,
)
