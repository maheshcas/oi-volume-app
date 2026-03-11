# OptionLens Architecture

## 1) Overview
OptionLens is a cache-first intraday options analytics app.

- Frontend: React + Vite + TypeScript (`frontend/`)
- Backend: FastAPI + background updater + async in-memory cache (`backend/`)

Design goals:
- Fetch NSE once per cycle.
- Compute intelligence centrally.
- Serve all users from cached snapshots.
- Keep request handlers read-only against cache.

## 2) Runtime Flow
1. `backend/app/main.py` starts FastAPI.
2. Startup launches the background refresh loop.
3. Every ~15 seconds, `backend/app/services/background_updater.py`:
   - fetches index, contract, and option-chain data
   - parses rows and summaries
   - runs the engine pipeline:
     - `preprocessing -> feature_engines -> regime_engine -> trap_engine -> conflict_resolver -> decision_engine -> stability_layer -> signal_priority -> trade_plan`
   - validates response consistency
   - writes cache atomically
4. API handlers read cache only.
5. On NSE failure, the last valid snapshot is retained and freshness degrades to stale/delayed.

## 3) Cache Design (`backend/app/core/cache.py`)
Stored state:
- `option_chain_data`, `summary_data`
- `last_update`, `last_successful_fetch`, `stale_data`, `is_fetching`
- metrics: `fetch_count`, `last_fetch_latency_ms`, `last_error`
- continuity memory: `previous_scores`, `score_history`, `previous_states`

Concurrency:
- guarded by `asyncio.Lock`
- `begin_fetch()/end_fetch()` prevents overlapping cycles

## 4) Backend Modules
### Services
- `app/services/nse_client.py`: NSE HTTP logic, retries, cookie session
- `app/services/parser.py`: strike-level shaping, dominance classification, interpretation text
- `app/services/background_updater.py`: orchestration, validation, cache writes, cycle logging
- `app/services/intraday_performance_tracker.py`: in-memory signal tracking and daily metrics
- `app/services/decision_engine.py`: legacy helper still used by updater glue code

### Engines
- `preprocessing.py`: normalized chain, ATM row, strike gap, PCR, ATR proxy, session phase, previous-cycle compatibility fields
- `oi_analyzer.py`: OI alignment/strength, rolling OI shift normalization, OI velocity score
- `volume_analyzer.py`: volume expansion, RVR, ATM participation, rolling volume normalization
- `sr_engine.py`: weighted support/resistance scoring, immediate/major levels, OI cluster zones, zone pressure
- `breakout_engine.py`: volatility-buffer breakout checks
- `trap_engine.py`: trap probability, wick scoring, hold-time scoring, liquidity absorption scoring, trap smoothing support
- `regime_engine.py`: trend/range/transition classification
- `decision_engine.py`: hybrid decision model with directional force, clarity, execution risk, primary/micro bias
- `target_engine.py`: targets, projections, expansion logic
- `trade_plan_engine.py`: concise trade plan generation
- `adaptive_calibration.py`: rolling weight calibration persistence

Additional engines in active use:
- `adaptive_weighting_engine.py`
- `bias_stability_engine.py`
- `expiry_mode_engine.py`
- `momentum_exhaustion_engine.py`
- `regime_shift_engine.py`
- `early_reversal_probability_engine.py`
- `exhaustion_trap_combo_engine.py`
- `auto_exit_suggestion_engine.py`
- `signal_priority_engine.py`
- `conflict_resolution_engine.py`
- `intraday_playbook_engine.py`

## 5) Strike Interpretation Layer
`backend/app/services/parser.py`

Strike dominance now uses PE share, not legacy 70/30 or delta-only logic.

Formula:
- `PE_percent = PE_OI / (PE_OI + CE_OI) * 100`

Labels:
- `PE Dominant`: `PE_percent >= 60`
- `CE Dominant`: `PE_percent <= 40`
- `Mixed`: `40 < PE_percent < 60`
- `Low Interest`: only when `CE_OI + PE_OI < MIN_STRIKE_TOTAL_OI`

Each strike now carries:
- `strike`
- `ce_oi`
- `pe_oi`
- `pe_percent`
- `dominance`
- `interpretation`

Interpretation text is one short sentence:
- PE dominant near support: `Strong put writing indicates support formation.`
- CE dominant above spot/resistance: `Call writers defending higher strikes.`
- Mixed: `Balanced positioning suggests market indecision.`
- Low interest: `Low participation at this strike.`

## 6) Support / Resistance Engine
`backend/app/engines/sr_engine.py`

Support and resistance are no longer chosen by highest OI alone.

Weighted strike strength:
- `strike_strength = 0.5 * normalized_oi + 0.3 * normalized_oi_change + 0.2 * proximity_to_spot`
- `proximity_to_spot = 1 - (abs(strike - spot) / max_strike_range)`

Computed separately for CE and PE.

Outputs:
- `support.immediate`, `support.major`
- `resistance.immediate`, `resistance.major`
- cluster zones:
  - `support_center`, `support_range`, `support_strength`
  - `resistance_center`, `resistance_range`, `resistance_strength`
- zone pressure:
  - `support_zone_pressure`, `support_zone_state`
  - `resistance_zone_pressure`, `resistance_zone_state`
- shift alerts:
  - `New Intraday Resistance Formed`
  - `Major Resistance Confirmed`
  - `Support Strengthening`

## 7) Decision Layer (Hybrid)
Decision engine separates slow and fast state:
- `primary_bias`
- `micro_bias`
- `directional_force`
- `clarity`
- `execution_risk`
- `state`
- `drift`

Stability layer in updater:
- 3-cycle bias confirmation
- 2-cycle projection confirmation
- low-conviction freeze (`confidence < 20` or `clarity < 40`)
- smoothed MSS (`0.7 * prev + 0.3 * current`)

## 8) MSS / Bias Conflict Layer
`background_updater.py`

Post-decision conflict detection does not change MSS or bias math.

Rules:
- `MSS <= 3` and `Bias == Bullish` -> `Transition Phase`
- `MSS >= 7` and `Bias == Bearish` -> `Transition Phase`
- `MSS 4-6` -> `Balanced Structure`

Response aliases now include:
- `market_state.market_structure_score`
- `market_state.mss_score`
- `market_state.structure_state`
- `market_state.structural_state`
- `market_state.structure_bias`

## 9) Trap Signals
Base trap engine remains unchanged.

Additional signal added in updater:
### OI Imbalance Trap Detector
- Near resistance:
  - if `CE_OIChangePct > 15` and `PE_OIChangePct < 5`
  - `trap_probability = 80`
  - `trap_reason = "Call writers defending resistance."`
- Near support:
  - if `PE_OIChangePct > 15` and `CE_OIChangePct < 5`
  - `support_strength = 80`
  - `support_reason = "Put writers strengthening support."`

Trap payload now may include:
- `trap_reason`
- `support_reason`
- `oi_imbalance_trap`

## 10) Response Validation
Before response return, updater validates:
- support strike should usually be `PE Dominant` or `Mixed`
- resistance strike should usually be `CE Dominant` or `Mixed`
- strong MSS/bias conflict

If inconsistent, response includes:
- `warnings: [...]`
- first warning normalized to `Signal conflict detected`

## 11) API Surface (`/api`)
Primary active endpoints:
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
- `/spot/live` is not part of current active API surface.
- API shape is backward compatible where possible; new fields are additive.

## 12) Frontend Structure
Main orchestrator:
- `frontend/src/App.tsx`

Core visible components:
- `MarketBanner.tsx`
- `DecisionBanner.tsx`
- `DecisionPanel.tsx`
- `KeyLevelsCard.tsx`
- `TrapCard.tsx`
- `StructuralChartCard.tsx`
- `TradePlanCard.tsx`
- `AdvancedAnalysisCard.tsx`

Current main-page layout:
- Decision Banner
- Decision Layer
- Key Levels
- Trap
- Structural Price Context
- Trade Plan
- Advanced Analysis above Daily Performance

Current UI notes:
- breakout targets are embedded inside `KeyLevelsCard`
- alerts render below the Trap card
- Trap card displays backend `trap_reason` / `support_reason` when present
- status bar uses one normalized regime source and separates:
  - spot
  - vs previous close
  - % change
  - from open
  - updated time

## 13) Freshness Semantics
Freshness states:
- `live`: `<30s`
- `stale`: `30-60s`
- `delayed`: `>60s`

Exposed by:
- `/health`
- `/api/health/nse`
- `/api/v2/intelligence/summary.market_state.{freshness_state,delta_seconds}`

## 14) Logging and Debugging
Cycle log:
- `backend/logs/optionlens_cycle_log.jsonl`

Logged diagnostics include:
- primary/micro bias
- drift
- directional force
- clarity
- execution risk
- trap probability and type
- support/resistance levels
- breakout strength
- rejection wick score
- hold-time ratio
- OI shift / OI velocity / volume expansion
- alignment score
- MSS and structure state
- validation warnings

Additional debug logs now include:
- strike dominance classification
- MSS/bias conflict resolution
- OI imbalance trap detection

## 15) Testing and Validation
Key validation commands:
- `python -m py_compile app/services/parser.py`
- `python -m py_compile app/services/background_updater.py`
- `python -m py_compile app/engines/sr_engine.py`

Existing tests:
- `backend/tests/test_sr_engine.py`
- `backend/tests/test_decision_engine_v4.py`
- `backend/tests/test_decision_engine_hybrid.py`
- `backend/tests/test_adaptive_calibration.py`

## 16) Operational Notes
- Keep heavy analytics in the background worker only.
- Keep request handlers cache-read only.
- Prefer additive response changes over breaking schema changes.
- For multi-instance deployment, replace process-local cache with Redis.
- Re-run compile checks and relevant tests after any rule-engine update.
