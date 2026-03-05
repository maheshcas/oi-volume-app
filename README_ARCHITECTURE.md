# OptionLens Architecture

## 1) Overview
OptionLens is a cache-first intraday options analytics app.

- Frontend: React + Vite + TypeScript + ECharts (`frontend/`)
- Backend: FastAPI + background updater + async in-memory cache (`backend/`)

Design goals:
- Fetch NSE once per cycle.
- Compute intelligence centrally.
- Serve all users from cached snapshots.

## 2) Runtime Flow
1. `app/main.py` starts FastAPI.
2. Startup launches `background_update_loop()` only.
3. Every ~15 seconds, `app/services/background_updater.py`:
   - fetches index + contract + option chain data
   - parses rows and summaries
   - runs engine pipeline
   - updates cache atomically
4. API handlers read cache only (no NSE calls in request path).
5. On NSE failure, last valid snapshot is retained; freshness turns stale/delayed.

## 3) Cache Design (`app/core/cache.py`)
State stored:
- `option_chain_data`, `summary_data`
- `last_update`, `last_successful_fetch`, `stale_data`, `is_fetching`
- `metrics`: `fetch_count`, `last_fetch_latency_ms`, `last_error`
- continuity memory: `previous_scores`, `score_history`, `previous_states`

Concurrency:
- guarded by `asyncio.Lock`
- `begin_fetch()/end_fetch()` prevents overlapping cycles

## 4) Backend Modules
### Services
- `app/services/nse_client.py`: NSE HTTP logic + retries + cookie session
- `app/services/parser.py`: strike-level interpretation shaping
- `app/services/background_updater.py`: orchestration + cache writer
- `app/services/intraday_performance_tracker.py`: signal logging + daily metrics
- `app/services/decision_engine.py`: legacy decision helper used by updater

### Engines
- `preprocessing.py`: normalized chain, ATM row, strike gap, PCR, ATR proxy
- `oi_analyzer.py`: OI alignment/strength/concentration
- `volume_analyzer.py`: volume expansion, RVR, ATM participation
- `sr_engine.py`: multi-tier S/R (`immediate` + `major`) + shift detection alerts
- `breakout_engine.py`: volatility-buffer breakout checks
- `trap_engine.py`: trap probability + confidence/volatility adjustment (with de-overlap scoring + proportional fake-breakout boost)
- `regime_engine.py`: trend/range/transition classification
- `decision_engine.py`: v4 hybrid decision model (3-axis: directional force, clarity, execution risk) with v3-compatible wrapper
- `bias_probability_engine.py`: retail bull/bear probability model
- `target_engine.py`: targets/projection generation
- `trade_plan_engine.py`: concise trade plan text
- `simulation_engine.py`: offline breakout/trap simulation
- `adaptive_calibration.py`: rolling 20-session weight calibration persistence

Additional specialized engines currently present:
- `adaptive_weighting_engine.py`
- `bias_stability_engine.py`
- `expiry_mode_engine.py`
- `momentum_exhaustion_engine.py`
- `regime_shift_engine.py`
- `early_reversal_probability_engine.py`
- `exhaustion_trap_combo_engine.py`
- `auto_exit_suggestion_engine.py`
- `signal_priority_engine.py`
- `arbitration_engine.py`
- `conflict_resolution_engine.py`

## 5) Decision Layer (Hybrid v4)
`decision_engine_v4` separates slow and fast market context:

- `primary_bias` (slow): flip-gated to reduce churn
- `micro_bias` (fast): per-cycle directional micro state
- 3-axis outputs:
  - `directional_force` (`bull`, `bear`, `strength`)
  - `clarity`
  - `execution_risk`
- `state` (retail-readable): Aggressive Trend / Cautious Trend / Standby / Range Play / Balanced
- `drift`: Strengthening / Weakening / Stable
- `retail_mapping`: text labels for force/clarity/risk

Primary bias flip gates:
- Normal sessions: force `>68`, clarity `>58`, sustained 3 cycles
- Midday: force `>75`, clarity `>60`, sustained 3 cycles

Memory persisted in cache state:
- `primary_bias`
- `rolling_force_history` (last 5)
- `rolling_clarity_history` (last 5)
- `last_primary_update_time`

## 6) API Surface (`/api`)
- `GET /option-chain/expiries`
- `GET /option-chain/summary`
- `GET /option-chain/target-projection`
- `GET /option-chain/interpretations`
- `GET /index-data`
- `GET /health/nse`
- `GET /v2/intelligence/summary`
- `GET /v2/intelligence/trade-plan`
- `GET /v2/performance/daily`
- `POST /bias/probability`
- `POST /simulation/breakout-performance`

Notes:
- `expiry` should be supplied for symbol+expiry specific summary lookups.
- `/spot/live` is not part of current active API surface.

## 7) Frontend Structure
Main orchestrator:
- `frontend/src/App.tsx`

Core components:
- `frontend/src/components/MarketBanner.tsx`
- `frontend/src/components/MarketStatePanel.tsx`
- `frontend/src/components/KeyLevelsCard.tsx`
- `frontend/src/components/TrapCard.tsx`
- `frontend/src/components/StructuralDiagnostics.tsx`

Fetch pattern:
- market strip: `/api/index-data`
- chain and analytics: `/api/option-chain/*`, `/api/v2/intelligence/*`

UI zones:
- fixed market/status banner
- market state layer (state + 3 meters + diagnostics)
- key levels + trap panel
- trade plan
- structural diagnostics (collapsible)
- tabs (overview/charts/heatmap/writers/basis/option-chain)

## 8) Freshness Semantics
Freshness states:
- `live`: `<30s`
- `stale`: `30-60s`
- `delayed`: `>60s`

Exposed by:
- `/health`
- `/api/health/nse`
- `/api/v2/intelligence/summary.market_state.{freshness_state,delta_seconds}`

## 9) Testing and Calibration
- Unit tests: `backend/tests/`
- Offline threshold calibration: `backend/calibration/threshold_calibrator.py`
- Hybrid/decision tests:
  - `backend/tests/test_decision_engine_v4.py`
  - `backend/tests/test_decision_engine_hybrid.py`
  - `backend/tests/test_adaptive_calibration.py`
  - `backend/tests/test_sr_engine.py`

## 10) Operational Notes
- Keep heavy analytics in background worker only.
- Keep request handlers cache-read only.
- For multi-instance deploy, replace process-local cache with Redis.
- Re-run tests after any rule-engine update.
