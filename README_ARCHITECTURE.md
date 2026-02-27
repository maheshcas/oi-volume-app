# OptionLens Architecture

## 1) System Overview
OptionLens is a two-tier app:
- Frontend: React + Vite + TypeScript + ECharts (`frontend/`)
- Backend: FastAPI + async cache + 15s background updater (`backend/`)

Design goal:
- Fetch NSE once per cycle (shared), serve many users from cache.
- Keep UI responsive with precomputed intelligence.

## 2) Repository Layout
```text
oi-volume-app/
├── backend/
│   └── app/
│       ├── main.py
│       ├── core/
│       │   └── cache.py
│       ├── routers/
│       │   └── option_chain.py
│       ├── services/
│       │   ├── background_updater.py
│       │   ├── nse_client.py
│       │   └── parser.py
│       ├── engines/
│       │   ├── preprocessing.py
│       │   ├── oi_analyzer.py
│       │   ├── volume_analyzer.py
│       │   ├── sr_engine.py
│       │   ├── breakout_engine.py
│       │   ├── trap_engine.py
│       │   ├── target_engine.py
│       │   ├── regime_engine.py
│       │   ├── decision_engine.py
│       │   ├── bias_probability_engine.py
│       │   └── simulation_engine.py
│       └── static/
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── styles.css
│       ├── components/
│       │   ├── MarketBanner.tsx
│       │   ├── DecisionPanel.tsx
│       │   ├── KeyLevelsCard.tsx
│       │   ├── StructuralDiagnostics.tsx
│       │   └── TrapCard.tsx
│       ├── auth/
│       └── lib/
└── README.md
```

## 3) Backend Runtime Flow
1. `main.py` starts FastAPI.
2. Startup launches `background_update_loop()`.
3. Every ~15s (`OPTIONLENS_REFRESH_SECONDS`), updater:
   - fetches index + option chain + contract info
   - parses rows (`parser.py`)
   - runs engine pipeline
   - writes full payload into in-memory cache
4. API routes read only from cache (no direct NSE calls in handlers).
5. If NSE fails, last valid snapshot is retained.

## 4) Cache Design (`core/cache.py`)
Stored state:
- `option_chain_data`, `summary_data`
- `last_update`, `last_successful_fetch`, `stale_data`
- `metrics` (`fetch_count`, `last_fetch_latency_ms`, `last_error`)
- bias smoothing state: `previous_scores`, `score_history`

Concurrency:
- `asyncio.Lock` guards read/write and fetch ownership.
- Overlapping cycles prevented via `begin_fetch()/end_fetch()`.

## 5) Engine Pipeline (Current Rules)
### 5.1 Preprocessing
- Normalizes strike rows and computes ATM row, strike gap, PCR, ATR proxy.

### 5.2 OI / Volume / S-R
- `oi_analyzer.py`: OI alignment, buildup type, OI strength, concentration.
- `volume_analyzer.py`: volume expansion, RVR, ATM participation.
- `sr_engine.py`: strongest CE resistance and PE support levels.

### 5.3 Breakout / Trap / Target
- `breakout_engine.py`: ATR-threshold breakout up/down.
- `trap_engine.py`:
  - base trap model (validity + trap raw)
  - volatility adjustment
  - confidence adjustment
  - trap classification and `show_affected_level`.
- `target_engine.py`: directional targets using support/resistance + ATR/expected move.

### 5.4 Regime + Decision
- `regime_engine.py`:
  - refined regime detection using ATR ratio, persistence (last 10 smoothed scores), breakout confirmation.
  - regime outputs: `trend` / `range` / `transition` (+ mapped labels)
  - returns adjusted weights + adjusted thresholds.
- `decision_engine.py`:
  - weighted score from OI/volume/ATM/breakout/regime
  - score smoothing using previous score (`alpha=0.4`)
  - probability + confidence
  - volatility modifier + volatility state (`Expanding`, `Stable`, `Contracting`)
  - structured outputs (`structure_score`, `alignment_ratio`, `primary_drivers`, `summary_statement`).

### 5.5 Bias Probability Engine
- `bias_probability_engine.py` computes:
  - `priceMomentumScore` (0-30)
  - `oiDirectionalScore` (0-30)
  - `volumeParticipationScore` (0-20)
  - `putCallImbalanceScore` (0-20)
- Combined score (0-100) => `bullishProbability`.
- `bearishProbability = 100 - bullishProbability`.
- Includes confidence and detailed score breakdown.

### 5.6 Parser Rule Engine
`services/parser.py` currently includes:
- Price/OI/Volume direction logic.
- Interpretation matrix:
  - Strong Long Build-up
  - Strong Short Build-up
  - Short Covering
  - Long Unwinding
  - Quiet Position Building
  - No Interest Zone
- Noise filtering.
- Strike ladder interpretation:
  - Call Writing / Put Writing / Balanced / Shift Building
  - strength levels.

### 5.7 Simulation Engine
- `simulation_engine.py` replays historical snapshots.
- For each snapshot computes S/R + breakout/trap and compares to next move.
- Returns: hit rate, false positive/negative rates, accuracy-over-time, detailed records.

## 6) Alert Arbitration Rules
In updater:
- Dominant direction = sign(smoothed score).
- Alerts classified:
  - `primary` if aligned
  - `counter` if opposite
- If `abs(smoothed_score) > 0.5`, counter alerts are suppressed.

## 7) Data Freshness Rules
Backend freshness state:
- `live`: delta < 30s
- `stale`: 30-60s
- `delayed`: > 60s

Exposed in:
- `/health/nse`
- `/v2/intelligence/summary` (`market_state.freshness_state`, `delta_seconds`)

## 8) API Surface (`routers/option_chain.py`)
- `GET /option-chain/expiries`
- `GET /option-chain/summary`
- `GET /option-chain/target-projection`
- `GET /option-chain/interpretations`
- `GET /index-data`
- `GET /health/nse`
- `GET /v2/intelligence/summary`
- `POST /bias/probability`
- `POST /simulation/breakout-performance`

## 9) Frontend Architecture
### 9.1 Composition
`App.tsx` orchestrates:
- data fetching, refresh, tab states, transformations
- wires backend payload into visual components

Primary components:
- `MarketBanner`: index, spot, regime, projection, trend, freshness/live badge.
- `DecisionPanel`: bias, bull/bear probability, confidence, trap risk, reversal risk.
- `KeyLevelsCard`: support/resistance/targets/acceleration zone.
- `StructuralDiagnostics`: collapsible diagnostics panel.
- `TrapCard`: trap probability/type/action card.

### 9.2 UI Zones
- Top status/banner
- Decision + levels + playbook cards
- Structural diagnostics (collapsible)
- Tabs:
  - `overview` (strike ladder + mini charts)
  - `charts` (OI chart)
  - `heatmap`
  - `writers`
  - `basis`
  - `option-chain` table
- Alert bar (primary/counter rendering)
- Disclaimer/footer

### 9.3 Rendering Rules
- Spot and directional arrows normalized to avoid encoding artifacts.
- Live badge color bound to backend freshness state.
- Counter alerts shown muted with label; can be suppressed by backend.

## 10) Operational Notes
- Backend is cache-first; routes should remain read-only to cache.
- NSE instability is handled by stale snapshot fallback.
- For production scaling, move cache to Redis if running multi-instance backend.
