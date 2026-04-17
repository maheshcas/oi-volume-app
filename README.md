# OptionLens

Real-time NSE/BSE options intelligence dashboard. FastAPI backend + React/TypeScript frontend.

---

## Quick Start

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\Activate        # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

**Production deployment** (single worker — required):
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 10000
```

---

## Architecture

```
backend/app/
├── domain/                         # Pure domain — no I/O, no FastAPI
│   ├── models/
│   │   ├── market.py               # MarketState, Bias, Regime (Pydantic)
│   │   ├── option_chain.py         # StrikeRow, OptionChainSnapshot
│   │   └── signals.py              # StrikeGuidance, TradePlan, TradeSignal
│   └── ports/
│       ├── market_feed.py          # IMarketFeed Protocol
│       └── state_store.py          # IStateStore Protocol
│
├── infrastructure/                 # External adapters (implements domain ports)
│   ├── feeds/
│   │   ├── nse_client.py           # NSE HTTP adapter
│   │   ├── bse_fetcher.py          # BSE option chain fetcher
│   │   └── bse_adapter.py          # BSE → internal schema adapter
│   └── persistence/
│       ├── daily_context.py        # Higher-timeframe daily context loader
│       ├── historical_zone_context.py
│       ├── historical_zone_scheduler.py
│       └── historical_zone_analysis.py
│
├── application/
│   └── use_cases/
│       └── background_updater.py   # Main async orchestration loop (~6 k lines)
│
├── presentation/
│   └── routers/
│       └── option_chain.py         # All FastAPI route handlers
│
├── engines/                        # Pure computation (no I/O)
│   ├── bias_probability_engine.py
│   ├── entry_target_engine.py
│   ├── sr_engine.py
│   ├── trap_engine.py
│   ├── regime_engine.py
│   ├── session_phase_engine.py
│   ├── material_breach_engine.py
│   ├── strike_intelligence_engine.py
│   ├── greeks_engine.py
│   ├── iv_rank_engine.py
│   ├── liquidity_map_engine.py
│   └── … (20+ engines total)
│
├── services/                       # Supporting services
│   ├── stability_logger.py
│   ├── engine_health.py
│   ├── intraday_performance_tracker.py
│   ├── spot_feed.py
│   └── parser.py
│
├── core/
│   └── cache.py                    # In-memory cache + make_cache_key()
│
├── auth.py                         # Supabase JWT middleware (async httpx)
├── dependencies.py                 # FastAPI Depends helpers
└── main.py                         # FastAPI app + lifespan

backend/scripts/
└── market_open_check.py            # Market-open verification (run at 09:15 IST)
```

---

## API Endpoints

### Market Intelligence

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/intelligence/summary` | Full market state, signals, regime, readiness, entry/target |
| GET | `/api/v2/performance/daily` | Daily signal accuracy and performance metrics |
| GET | `/api/option-chain/expiries` | Available expiries for a symbol |
| GET | `/api/option-chain/summary` | Raw option chain summary |

**Common query params:** `symbol=NIFTY`, `instrument_type=Indices`, `expiry=27-Jun-2024`

Supported symbols: `NIFTY`, `BANKNIFTY`, `FINNIFTY`, `SENSEX`
(extend via `OPTIONLENS_SYMBOLS` env var)

### Diagnostics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health/nse` | NSE feed freshness: `freshness_state`, `delta_seconds`, `stale_data` |
| GET | `/engine-health` | Engine contribution stats from last 200 cycle log entries |
| GET | `/event-log` | Recent market events (last N, default 20, max 200) |
| GET | `/health` | App-level health: cache status + last_update |

### Auth (Supabase JWT)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analysis` | Protected example endpoint |

Pass `Authorization: Bearer <supabase_access_token>`.

---

## Key Signal Contract (`market_state`)

Fields exposed in `/api/v2/intelligence/summary → market_state`:

```
bias / bullish_probability / bearish_probability
trade_readiness / readiness_state / readiness_active
committed_regime / detected_regime / session_phase
support / resistance / previous_support / previous_resistance
trap_probability / trap_type / trap_direction / trap_affected_level
directional_pressure_score / dps_adjusted / pressure_state
oi_scenario / dps_scenario_multiplier
entry_target { trade_type, entry_underlying, entry_option_strike,
               entry_option_type, entry_option_action, entry_premium,
               stop_underlying, stop_premium_value, target_1, target_2,
               rr_t1, rr_t2, price_magnet_strike, compression_zone, … }
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000,…` | CORS origin allowlist (comma-separated) |
| `ALLOWED_ORIGIN_REGEX` | Netlify + optionlens.in pattern | Regex for additional CORS origins |
| `OPTIONLENS_SYMBOLS` | `NIFTY,BANKNIFTY,FINNIFTY` | Symbols polled by background updater |
| `OPTIONLENS_ENABLE_CYCLE_LOG` | `false` | Enable JSONL cycle log |
| `OPTIONLENS_ENABLE_EVENT_LOG` | `false` | Enable market event log |
| `OPTIONLENS_ENABLE_STABILITY_LOGGER` | `false` | Enable stability snapshot logger |
| `SUPABASE_URL` | — | Supabase project URL for JWT verification |
| `SUPABASE_ANON_KEY` | — | Supabase anon key |

---

## Market-Open Verification Script

Polls the running backend for 5 health checks in the first 15 minutes after 09:15 IST.

```bash
python scripts/market_open_check.py
python scripts/market_open_check.py --url http://localhost:8000 --symbols NIFTY --interval 15 --window 15
```

Checks:
1. `freshness_state=live` and `stale_data=false` and timestamp IST ≥ 09:15
2. `oi_shift_score` or `oi_velocity_score` > 0 (live OI flowing)
3. `session_phase` contains "Opening" / "Drive"
4. `directional_reason` contains wall_ratio > 0.05x
5. `total_signals_logged` > 0 in performance endpoint

Exits 0 if all five pass, 1 on timeout.

---

## Data Flow

```
NSE/BSE APIs
    │
    ▼
infrastructure/feeds/  (nse_client, bse_fetcher, bse_adapter)
    │
    ▼
application/use_cases/background_updater.py   ← async loop, ~3 s cycle
    │  calls engines/* (pure computation)
    │  reads infrastructure/persistence/* (daily context, historical zones)
    │  writes to core/cache.py
    │
    ▼
core/cache.py   (in-memory, single worker)
    │
    ▼
presentation/routers/option_chain.py   ← FastAPI serves cached state
    │
    ▼
Frontend (React/TypeScript)
```

---

## Deployment Notes

- **Single Uvicorn worker required.** The background updater uses module-level in-memory state dicts. Multiple workers fork this state, causing history divergence.
- **CORS:** Set `ALLOWED_ORIGINS` env var on Render to the deployed Netlify URL. Wildcard `*` is never combined with `allow_credentials=True`.
- **Auth:** JWKS is fetched via `httpx.AsyncClient` (non-blocking). Cache TTL = 1 hour.
- **Log files** resolve relative to the backend root via `Path(__file__).resolve().parents[N]`; depths are calibrated per-file after the clean architecture migration.
