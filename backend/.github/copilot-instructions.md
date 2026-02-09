# Copilot Instructions for NSE OI-Volume Backend

## Architecture Overview

**Core Purpose**: FastAPI service that fetches NSE NIFTY option chain data and analyzes Open Interest vs Volume to generate trading signals.

**Data Flow**:
1. **HTTP Router** ([app/routers/option_chain.py](app/routers/option_chain.py#L9)) → receives `/option-chain/summary` requests
2. **NSE Client** ([app/services/nse_client.py](app/services/nse_client.py)) → fetches raw JSON from NSE API with session/cookie handling
3. **Parser** ([app/services/parser.py](app/services/parser.py)) → extracts CE/PE metrics and generates "Bullish/Bearish/Neutral" signals
4. **Response** → returns array of strike-level analysis with OI, volume, and signal

## Key Development Patterns

### Testing Without NSE API
Use `use_sample=True` query parameter to bypass live NSE requests:
```
GET /option-chain/summary?use_sample=true
```
This loads sample data from `app/services/nifty_option_chain.json` for local development/testing.

### Signal Generation Logic
Signal logic in `parser.py` uses simple heuristics (lines 26-31):
- **PE Buildup (Bearish)**: `PE_ΔOI > CE_ΔOI AND PE_Volume > CE_Volume`
- **CE Buildup (Bullish)**: `CE_ΔOI > PE_ΔOI AND CE_Volume > PE_Volume`
- **Neutral**: Otherwise

When extending signals, maintain this pattern: compare change-in-OI AND volume for both legs.

### NSE API Integration
The NSE client requires:
- User-Agent header and Accept-Language (avoid NSE blocking)
- Initial session GET to NSE homepage to acquire cookies
- Session reuse for subsequent API calls
- Timeout handling for unreliable networks

See [app/services/nse_client.py](app/services/nse_client.py#L12-L19) for current implementation.

## Project Setup

```powershell
# Activate virtual environment
python -m venv venv
venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python -m uvicorn backend.app.main:app --reload
```

## Data Model Notes

NSE option chain response structure (returned by `fetch_option_chain`):
```python
{
  "records": {
    "underlyingValue": 23500.0,  # Spot price
    "data": [
      {
        "strikePrice": 23000,
        "CE": { "openInterest": 100, "changeinOpenInterest": 50, "totalTradedVolume": 1000 },
        "PE": { "openInterest": 200, "changeinOpenInterest": 25, "totalTradedVolume": 500 }
      },
      ...
    ]
  }
}
```

When modifying parser logic, reference actual NSE field names (case-sensitive).

## Common Tasks

- **Add new signal type**: Modify signal logic in `parser.py` → add CE/PE field comparisons → update enum/response type
- **Change API behavior**: Router query params are defined in `option_chain.py` → controls sample vs live mode
- **Debug NSE requests**: Check `nse_client.py` HEADERS and timeout; NSE may require User-Agent rotation
