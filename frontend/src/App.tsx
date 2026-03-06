import { useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import TrapCard from "./components/TrapCard";
import MarketBanner from "./components/MarketBanner";
import DecisionPanel from "./components/DecisionPanel";
import KeyLevelsCard from "./components/KeyLevelsCard";
import StructuralDiagnostics from "./components/StructuralDiagnostics";
import MarketPlaybookCard from "./components/MarketPlaybookCard";
import ExpansionTargetsCard from "./components/ExpansionTargetsCard";
import RetailSummaryStrip from "./components/RetailSummaryStrip";
import EngineHealthPanel, { type EngineHealthResponse } from "./components/EngineHealthPanel";
import { MARKETING_MODE } from "./config/uiMode";

type SummaryRow = {
  strike: number;
  spot: number;
  CE_OI: number;
  CE_DeltaOI: number;
  CE_Volume: number;
  CE_LastPrice?: number;
  CE_PriceChange?: number;
  CE_PriceDir?: string;
  CE_OIDir?: string;
  CE_VolDir?: string;
  CE_Interpretation?: string;
  CE_InterpretationDesc?: string;
  CE_ConfidenceScore?: number;
  CE_TruthFlags?: {
    volume_without_oi: boolean;
    oi_without_volume: boolean;
    real_money: boolean;
    volume_low: boolean;
  };
  PE_OI: number;
  PE_DeltaOI: number;
  PE_Volume: number;
  PE_LastPrice?: number;
  PE_PriceChange?: number;
  PE_PriceDir?: string;
  PE_OIDir?: string;
  PE_VolDir?: string;
  PE_Interpretation?: string;
  PE_InterpretationDesc?: string;
  PE_ConfidenceScore?: number;
  PE_TruthFlags?: {
    volume_without_oi: boolean;
    oi_without_volume: boolean;
    real_money: boolean;
    volume_low: boolean;
  };
  signal: string;
};

type SummaryResponse = {
  meta: {
    symbol: string;
    instrument_type: string;
    expiry: string | null;
    spot: number | null;
    timestamp: string | null;
  };
  target_projection?: {
    state: "RANGE" | "BREAKOUT_UP" | "BREAKOUT_DOWN";
    spot: number;
    support: number;
    resistance: number;
    rangeWidth: number;
    midPoint: number;
    distanceToSupport: number;
    distanceToResistance: number;
    breakBuffer: number;
    midpointBuffer: number;
    targetMode?: string;
    confidenceScore?: number;
    volatilityMethod?: string;
    atmCallLtp?: number;
    atmPutLtp?: number;
    expectedMove?: number;
    structuralRange?: number;
    blendedMove?: number;
    projectedMove?: number;
    direction: string;
    targetPrimary: number | null;
    targetSecondary: number | null;
    targetNote: string | null;
    confirmation?: {
      bullish?: {
        atm_oi_rising: boolean;
        ce_unwinding: boolean;
        pe_aggressive_build: boolean;
        confirmed: boolean;
      };
      bearish?: {
        pe_unwinding: boolean;
        ce_aggressive_build: boolean;
        pcr_below_085: boolean;
        confirmed: boolean;
      };
      pcr?: number | null;
      atmStrike?: number | null;
    };
  } | null;
  rows: SummaryRow[];
};

type HistoryPoint = {
  fetchedAtMs: number;
  label: string;
  spot: number | null;
  rows: SummaryRow[];
};

type IntelligenceResponse = {
  market_state?: {
    bias: "Bullish" | "Bearish" | "Neutral";
    probability_bull: number;
    probability_bear: number;
    confidence: number;
    clarity?: number;
    trap_risk?: number;
    reversal_risk?: number;
    support?: number;
    resistance?: number;
    support_zone_pressure?: number;
    support_zone_state?: string;
    resistance_zone_pressure?: number;
    resistance_zone_state?: string;
    target1?: number;
    target2?: number;
    summary_line?: string;
    state?: string;
    primary_bias?: "Bullish" | "Bearish" | "Neutral";
    composite_score?: number;
    adaptive_mode?: "Active" | "Base" | string;
    adaptive_weights?: {
      oi?: number;
      volume?: number;
      breakout?: number;
      sr?: number;
    };
    alignment_ratio?: number;
    volatility_state?: "Expanding" | "Contracting" | "Stable";
    freshness_state?: "live" | "stale" | "delayed";
    delta_seconds?: number | null;
    market_structure_score?: number;
    structure_state?: string;
    drift?: string;
    projection?: string;
    conflict_market_state?: string;
    conflict_flags?: string[];
    directional_force?: {
      bull?: number;
      bear?: number;
      strength?: number;
    };
  };
  levels?: {
    support?: {
      strike?: number;
      score?: number;
      range?: [number | null, number | null] | null;
      zone_pressure?: number;
      zone_state?: string;
    };
    resistance?: {
      strike?: number;
      score?: number;
      range?: [number | null, number | null] | null;
      zone_pressure?: number;
      zone_state?: string;
    };
    target_1?: number | null;
    target_2?: number | null;
    acceleration_zone?: string | null;
  };
  signals?: {
    oi?: {
      oi_velocity_score?: number;
    };
    breakout?: {
      breakout_strength?: number;
    };
    alerts?: Array<{
      message: string;
      direction: "up" | "down" | "neutral";
      type: "primary" | "counter";
    }>;
    trap?: {
      trap_probability_pct?: number;
      trap_risk?: number;
      trap_level?: "Low" | "Moderate" | "High";
      trap_type?: string;
      show_affected_level?: boolean;
      validity_score?: number;
      trap_raw?: number;
    };
    momentum_exhaustion?: {
      momentum_exhaustion?: boolean;
      exhaustion_type?: string | null;
    };
    auto_exit?: {
      exit_signal?: boolean;
      exit_reason?: string | null;
    };
    expiry_adaptive?: {
      expiry_mode?: boolean;
      expiry_multiplier?: number;
      trap_risk?: number;
      pinning_risk?: boolean;
      adjustedMove?: number;
    };
    alignment_filter?: {
      alignment_score?: number;
      price_momentum?: number;
      oi_shift_score?: number;
      volume_expansion_score?: number;
      breakout_suppressed?: boolean;
    };
  };
  trade_plan?: {
    strategy_type?: string;
    entry_zone?: string;
    stop_hint?: string;
    target_primary?: number | null;
    target_extended?: number | null;
    caution_note?: string;
  };
  intraday_playbook?: {
    bias?: string;
    regime?: string;
    strategy?: string;
    support_zone?: Array<number | null> | string | null;
    resistance_zone?: Array<number | null> | string | null;
    expansion_target?: number | null;
  };
};

type UiAlert = {
  message: string;
  type: "primary" | "counter";
  severity: "info" | "watch" | "high";
};

type DailyPerformance = {
  bias_accuracy_percent: number;
  trap_accuracy_percent: number;
  exit_accuracy_percent: number;
  total_signals_logged: number;
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/+$/, "");
const REFRESH_MS = 15000;
const SPOT_REFRESH_MS = 2000;
const HEATMAP_WINDOW_MINUTES = 120;
const LIVE_DATA_UNAVAILABLE_MSG =
  "Live data temporarily unavailable. Showing last valid snapshot.";
const TRAP_BREAK_BUFFER_PCT_DEFAULT = 0.1;
const TRAP_BREAK_BUFFER_PCT_BANKNIFTY = 0.15;
const LOW_OI_CONFIRM_RATIO = 0.6;
const LOW_VOLUME_CONFIRM_RATIO = 0.8;
const ATM_BAND_RANGE = 2;
const SHORT_COVERING_BURST_MIN_STRIKES = 2;
const ATM_VOLUME_SHOCK_MULTIPLIER = 1.4;

const SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY"];
const INDEX_NAMES = ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE"];

function classifyAlertSeverity(message: string): "info" | "watch" | "high" {
  const text = String(message || "").toLowerCase();
  if (
    text.includes("shock") ||
    text.includes("spike") ||
    text.includes("trap") ||
    text.includes("reversal") ||
    text.includes("exhaustion") ||
    text.includes("breakdown")
  ) {
    return "high";
  }
  if (
    text.includes("breakout") ||
    text.includes("resistance") ||
    text.includes("support") ||
    text.includes("watch")
  ) {
    return "watch";
  }
  return "info";
}

function alertPriority(item: UiAlert): number {
  const text = String(item.message || "").toLowerCase();
  if (text.includes("trap")) return 1;
  if (text.includes("breakout") || text.includes("breakdown")) return 2;
  if (text.includes("target") || text.includes("expansion")) return 3;
  return 4;
}

type IndexRow = {
  indexName: string;
  last: number;
  previousClose?: number;
  percChange: number;
  timeVal: string;
};

function formatNumber(value: number | string | null | undefined) {
  if (value === null || value === undefined) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString("en-IN");
}

function formatSigned(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}`;
}

function buildDecisionSummary(
  bias: "Bullish" | "Bearish" | "Neutral",
  support: number | null | undefined,
  resistance: number | null | undefined,
  fallback: string
) {
  const supportTxt =
    typeof support === "number" && !Number.isNaN(support) ? support.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : null;
  const resistanceTxt =
    typeof resistance === "number" && !Number.isNaN(resistance) ? resistance.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : null;

  if (bias === "Bullish" && supportTxt) {
    return `Structure favors upside while support holds at ${supportTxt}.`;
  }
  if (bias === "Bearish" && resistanceTxt) {
    return `Structure favors downside while resistance holds at ${resistanceTxt}.`;
  }
  if (supportTxt && resistanceTxt) {
    return `Structure is balanced between support ${supportTxt} and resistance ${resistanceTxt}.`;
  }
  return fallback;
}

type DirectionKind = "up" | "down" | "flat";

function normalizeDirection(direction?: string): DirectionKind {
  const d = String(direction ?? "").trim().toUpperCase();
  if (d === "\u2191" || d === "\u25B2" || d === "UP") return "up";
  if (d === "\u2193" || d === "\u25BC" || d === "DOWN") return "down";
  return "flat";
}

function directionArrow(direction?: string) {
  const kind = normalizeDirection(direction);
  if (kind === "up") return "\u25B2";
  if (kind === "down") return "\u25BC";
  return "\u2192";
}

type TrapStrikeData = {
  strike: number;
  ceOIChange: number;
  peOIChange: number;
  ceVolume: number;
  peVolume: number;
};

type TrapMarketContext = {
  symbol: string;
  spot: number;
  resistance: number;
  support: number;
  strikes: TrapStrikeData[];
};

function getBreakBufferPct(symbol: string) {
  if (symbol === "BANKNIFTY") return TRAP_BREAK_BUFFER_PCT_BANKNIFTY;
  return TRAP_BREAK_BUFFER_PCT_DEFAULT;
}

function getATMIndex(strikes: TrapStrikeData[], spot: number) {
  let closestIndex = 0;
  let minDiff = Number.POSITIVE_INFINITY;
  strikes.forEach((s, i) => {
    const diff = Math.abs(s.strike - spot);
    if (diff < minDiff) {
      minDiff = diff;
      closestIndex = i;
    }
  });
  return closestIndex;
}

function getATMBand(strikes: TrapStrikeData[], atmIndex: number) {
  return strikes.slice(
    Math.max(0, atmIndex - ATM_BAND_RANGE),
    Math.min(strikes.length, atmIndex + ATM_BAND_RANGE + 1)
  );
}

function checkWeakDirectionalOI(
  context: TrapMarketContext,
  breakoutUp: boolean,
  breakoutDown: boolean
) {
  const { strikes, spot } = context;
  const atmIndex = getATMIndex(strikes, spot);
  const atmBand = getATMBand(strikes, atmIndex);
  const globalAvgOI =
    strikes.reduce((sum, s) => sum + Math.abs(s.ceOIChange) + Math.abs(s.peOIChange), 0) /
    Math.max(1, strikes.length);
  const atmAvgOI =
    atmBand.reduce((sum, s) => sum + Math.abs(s.ceOIChange) + Math.abs(s.peOIChange), 0) /
    Math.max(1, atmBand.length);
  const weakParticipation = atmAvgOI < globalAvgOI * LOW_OI_CONFIRM_RATIO;

  if (breakoutUp) {
    const directionalSupport = atmBand.some((s) => s.ceOIChange < 0 || s.peOIChange > 0);
    return { weakParticipation, directionalSupport, weakDirectional: weakParticipation || !directionalSupport };
  }
  if (breakoutDown) {
    const directionalSupport = atmBand.some((s) => s.peOIChange < 0 || s.ceOIChange > 0);
    return { weakParticipation, directionalSupport, weakDirectional: weakParticipation || !directionalSupport };
  }
  return { weakParticipation, directionalSupport: true, weakDirectional: false };
}

function checkWeakVolume(context: TrapMarketContext) {
  const { strikes, spot } = context;
  const atmIndex = getATMIndex(strikes, spot);
  const atmBand = getATMBand(strikes, atmIndex);
  const globalAvgVolume =
    strikes.reduce((sum, s) => sum + s.ceVolume + s.peVolume, 0) / Math.max(1, strikes.length);
  const atmAvgVolume =
    atmBand.reduce((sum, s) => sum + s.ceVolume + s.peVolume, 0) / Math.max(1, atmBand.length);
  return atmAvgVolume < globalAvgVolume * LOW_VOLUME_CONFIRM_RATIO;
}

function detectTrap(context: TrapMarketContext) {
  const { symbol, spot, resistance, support } = context;
  const breakBuffer = spot * (getBreakBufferPct(symbol) / 100);
  const breakoutUp = spot > resistance + breakBuffer;
  const breakoutDown = spot < support - breakBuffer;
  if (!breakoutUp && !breakoutDown) {
    return {
      bullTrap: false,
      bearTrap: false,
      trapLikely: false,
      message: "No trap setup",
      trapScore: 0,
      trapRisk: "Safe breakout",
      weakParticipation: false,
      volumeExpansion: false,
    };
  }

  const oiCheck = checkWeakDirectionalOI(context, breakoutUp, breakoutDown);
  const weakVolume = checkWeakVolume(context);
  const volumeExpansion = !weakVolume;
  const bullTrap = breakoutUp && oiCheck.weakDirectional && weakVolume;
  const bearTrap = breakoutDown && oiCheck.weakDirectional && weakVolume;
  const trapLikely = bullTrap || bearTrap;
  let trapScore = 0;
  if (breakoutUp || breakoutDown) trapScore += 40;
  if (oiCheck.weakParticipation) trapScore += 30;
  if (!volumeExpansion) trapScore += 30;
  const trapRisk =
    trapScore <= 30 ? "Safe breakout" : trapScore <= 60 ? "Caution" : "High Trap Risk";

  let message = "No trap setup";
  if (bullTrap) {
    message =
      "Breakout above resistance lacks directional OI and volume confirmation: possible bull trap";
  } else if (bearTrap) {
    message =
      "Breakdown below support lacks directional OI and volume confirmation: possible bear trap";
  }

  return {
    bullTrap,
    bearTrap,
    trapLikely,
    message,
    trapScore,
    trapRisk,
    weakParticipation: oiCheck.weakParticipation,
    volumeExpansion,
  };
}

export default function App() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [instrumentType, setInstrumentType] = useState("Indices");
  const [expiries, setExpiries] = useState<string[]>([]);
  const [expiry, setExpiry] = useState<string>("");
  const [rangeEnabled, setRangeEnabled] = useState(true);
  const [rangeCount, setRangeCount] = useState(10);
  const [rows, setRows] = useState<SummaryRow[]>([]);
  const [meta, setMeta] = useState<SummaryResponse["meta"] | null>(null);
  const [status, setStatus] = useState<string>("Idle");
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [useSample, setUseSample] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [nseStatus, setNseStatus] = useState<"ok" | "blocked" | "checking">("checking");
  const [nseMessage, setNseMessage] = useState<string>("");
  const [indexData, setIndexData] = useState<IndexRow[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [apiTargetProjection, setApiTargetProjection] = useState<SummaryResponse["target_projection"]>(null);
  const [intelligence, setIntelligence] = useState<IntelligenceResponse | null>(null);
  const [dailyPerformance, setDailyPerformance] = useState<DailyPerformance | null>(null);
  const [engineHealth, setEngineHealth] = useState<EngineHealthResponse | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "charts" | "heatmap" | "writers" | "basis" | "option-chain" | "engine-health"
  >("overview");
  const [showStructural, setShowStructural] = useState(false);
  const [showDailyPerformance, setShowDailyPerformance] = useState(false);
  const [showTradePlan, setShowTradePlan] = useState(false);
  const [showMoreAlerts, setShowMoreAlerts] = useState(false);
  const [stableBadges, setStableBadges] = useState({
    structure: "-",
    pressure: "Stable",
    trap: "Low",
  });
  const [pressureSmoothed, setPressureSmoothed] = useState(50);
  const [readinessDisplay, setReadinessDisplay] = useState<{
    score: number;
    state: "WAIT" | "CAUTION" | "READY";
  }>({ score: 0, state: "WAIT" });
  const readinessPendingRef = useRef<{ score: number; state: "WAIT" | "CAUTION" | "READY"; count: number }>({
    score: 0,
    state: "WAIT",
    count: 0,
  });
  const pendingBadgeRef = useRef({
    structure: { value: "-", count: 0 },
    pressure: { value: "Stable", count: 0 },
    trap: { value: "Low", count: 0 },
  });

  async function loadExpiries() {
    setStatus("Loading expiries...");
    try {
      const params = new URLSearchParams({
        symbol,
        instrument_type: instrumentType,
        use_sample: useSample ? "true" : "false",
      });
      const res = await fetch(`${API_BASE}/option-chain/expiries?${params}`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data.expiries) ? data.expiries : [];
      setExpiries(list);
      setExpiry((current) => (current && list.includes(current) ? current : list[0] ?? ""));
      setStatus(list.length ? `Loaded ${list.length} expiries.` : "No expiries returned.");
    } catch {
      setStatus(LIVE_DATA_UNAVAILABLE_MSG);
      setExpiries([]);
      setExpiry("");
    }
  }

  async function loadSummary() {
    if (!expiry) return;
    setStatus("Fetching option chain...");
    try {
      const params = new URLSearchParams({
        symbol,
        instrument_type: instrumentType,
        expiry,
        use_sample: useSample ? "true" : "false",
      });
      const res = await fetch(`${API_BASE}/option-chain/summary?${params}`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = (await res.json()) as SummaryResponse;
      setRows(data.rows ?? []);
      setMeta(data.meta ?? null);
      setApiTargetProjection(data.target_projection ?? null);
      const fetchedAt = Date.now();
      const displayLabel = new Date(fetchedAt).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      });
      setLastUpdated(new Date(fetchedAt).toLocaleTimeString("en-IN"));
      setHistory((prev) => {
        const minTs = fetchedAt - HEATMAP_WINDOW_MINUTES * 60 * 1000;
        const next = [
          ...prev.filter((point) => point.fetchedAtMs >= minTs),
          {
            fetchedAtMs: fetchedAt,
            label: displayLabel,
            spot: typeof data.meta?.spot === "number" ? data.meta.spot : null,
            rows: data.rows ?? [],
          },
        ];
        // avoid rendering oversized heatmap payload in long-running sessions
        return next.slice(-480);
      });
      setStatus(`Loaded ${data.rows?.length ?? 0} strikes.`);

      // v2 intelligence (single source of truth for bias/regime/probabilities)
      try {
        const resV2 = await fetch(`${API_BASE}/v2/intelligence/summary?${params}`);
        if (resV2.ok) {
          const dataV2 = (await resV2.json()) as IntelligenceResponse;
          setIntelligence(dataV2);
        }
        const resPerf = await fetch(`${API_BASE}/v2/performance/daily?${params}`);
        if (resPerf.ok) {
          const perf = (await resPerf.json()) as DailyPerformance;
          setDailyPerformance(perf);
        }
      } catch {
        // Keep existing UI state if v2 call fails.
      }
    } catch {
      setStatus(LIVE_DATA_UNAVAILABLE_MSG);
      // Preserve last valid snapshot instead of clearing UI.
    }
  }

  async function loadIndexData() {
    try {
      const params = new URLSearchParams({ names: INDEX_NAMES.join(",") });
      const res = await fetch(`${API_BASE}/index-data?${params}`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data.data) ? data.data : [];
      if (list.length > 0) {
        setIndexData(list);
      }
    } catch {
      setStatus((current) => `${current} | Index data unavailable`);
      // Keep last valid snapshot on transient live-feed failures.
    }
  }

  async function loadEngineHealth() {
    if (MARKETING_MODE) return;
    try {
      const res = await fetch(`${API_BASE}/engine-health`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = (await res.json()) as EngineHealthResponse;
      setEngineHealth(data);
    } catch {
      // keep last successful health snapshot
    }
  }

  async function checkNseHealth() {
    setNseStatus("checking");
    setNseMessage("");
    try {
      const res = await fetch(`${API_BASE}/health/nse`);
      if (!res.ok) {
        throw new Error("NSE unavailable");
      }
      setNseStatus("ok");
    } catch {
      setNseStatus("blocked");
      setNseMessage(LIVE_DATA_UNAVAILABLE_MSG);
    }
  }

  async function handleManualRefresh() {
    await checkNseHealth();
    await loadIndexData();
    await loadSummary();
    await loadEngineHealth();
  }

  useEffect(() => {
    setExpiry("");
    loadExpiries();
  }, [symbol, instrumentType, useSample]);

  useEffect(() => {
    if (!expiry) return;
    checkNseHealth();
    loadIndexData();
    loadSummary();
    loadEngineHealth();
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      checkNseHealth();
      loadIndexData();
      loadSummary();
      loadEngineHealth();
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [expiry, symbol, instrumentType, useSample, autoRefresh]);

  useEffect(() => {
    if (!expiry) return;
    loadIndexData();
    const timer = setInterval(() => {
      loadIndexData();
    }, SPOT_REFRESH_MS);
    return () => clearInterval(timer);
  }, [expiry, symbol]);

  const filteredRows = useMemo(() => rows, [rows]);
  const rangeFilteredRows = useMemo(() => {
    if (!rangeEnabled) return filteredRows;
    if (!rows.length) return rows;
    const numericStrikes = rows
      .map((row) => Number(row.strike))
      .filter((value) => !Number.isNaN(value))
      .sort((a, b) => a - b);
    const spot = meta?.spot ?? null;
    if (spot === null || numericStrikes.length === 0) return rows;
    let closestIndex = 0;
    let closestDiff = Number.POSITIVE_INFINITY;
    numericStrikes.forEach((strike, index) => {
      const diff = Math.abs(strike - spot);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = index;
      }
    });
    const count = Math.max(0, Math.min(rangeCount, Math.floor(numericStrikes.length / 2)));
    const start = Math.max(0, closestIndex - count);
    const end = Math.min(numericStrikes.length - 1, closestIndex + count);
    const allowed = new Set(numericStrikes.slice(start, end + 1).map(String));
    return rows.filter((row) => allowed.has(String(row.strike)));
  }, [filteredRows, rows, rangeEnabled, rangeCount, meta?.spot]);

  const displayRows = rangeFilteredRows;
  const displayStrikes = useMemo(() => displayRows.map((row) => row.strike), [displayRows]);
  const displayCeOi = useMemo(() => displayRows.map((row) => row.CE_OI), [displayRows]);
  const displayPeOi = useMemo(() => displayRows.map((row) => row.PE_OI), [displayRows]);
  const displayCeVol = useMemo(() => displayRows.map((row) => row.CE_Volume), [displayRows]);
  const displayPeVol = useMemo(() => displayRows.map((row) => row.PE_Volume), [displayRows]);

  const nearestSpotStrike = useMemo(() => {
    if (!displayRows.length) return null;
    const spot = meta?.spot ?? null;
    if (spot === null) return null;
    let nearest = displayRows[0].strike;
    let minDiff = Math.abs(Number(nearest) - spot);
    displayRows.forEach((row) => {
      const diff = Math.abs(Number(row.strike) - spot);
      if (diff < minDiff) {
        minDiff = diff;
        nearest = row.strike;
      }
    });
    return nearest;
  }, [displayRows, meta?.spot]);

  const oiOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: { data: ["Put OI", "Call OI"], textStyle: { color: "#f8f5ee" } },
      grid: { left: 48, right: 32, top: 32, bottom: 60 },
      xAxis: {
        type: "category",
        data: displayStrikes,
        axisLabel: { color: "#d2d8d8", rotate: 45 },
      },
      yAxis: [
        { type: "value", axisLabel: { color: "#d2d8d8" } },
        { type: "value", axisLabel: { color: "#d2d8d8" } },
      ],
      series: [
        { name: "Put OI", type: "bar", data: displayPeOi, itemStyle: { color: "#58df7c" } },
        {
          name: "Call OI",
          type: "bar",
          data: displayCeOi,
          itemStyle: { color: "#f06c6c" },
          markLine: nearestSpotStrike
            ? {
                symbol: "none",
                label: {
                  formatter: `${meta?.symbol ?? "Spot"} ${meta?.spot ?? ""}`,
                  color: "#e6e6e6",
                },
                lineStyle: { color: "#e6e6e6", width: 2, type: "dashed" },
                data: [{ xAxis: String(nearestSpotStrike) }],
              }
            : undefined,
        },
        {
          name: "CE Volume",
          type: "line",
          yAxisIndex: 1,
          data: displayCeVol,
          smooth: true,
          lineStyle: { color: "#e6e6e6", width: 2 },
          itemStyle: { color: "#e6e6e6" },
        },
        {
          name: "PE Volume",
          type: "line",
          yAxisIndex: 1,
          data: displayPeVol,
          smooth: true,
          lineStyle: { color: "#f3c063", width: 2 },
          itemStyle: { color: "#f3c063" },
        },
      ],
    }),
    [displayStrikes, displayCeOi, displayPeOi, nearestSpotStrike, meta?.symbol, meta?.spot]
  );

  const indexNameMap: Record<string, string> = {
    NIFTY: "NIFTY 50",
    BANKNIFTY: "NIFTY BANK",
    FINNIFTY: "NIFTY FIN SERVICE",
  };
  const indexRow = indexData.find((row) => row.indexName === indexNameMap[symbol]);
  // Prefer index quote for faster visible updates; fallback to option-chain spot.
  const spotValue = indexRow?.last ?? meta?.spot ?? null;
  const strikesSorted = useMemo(
    () => [...displayRows].sort((a, b) => Number(a.strike) - Number(b.strike)),
    [displayRows]
  );
  const strikeSlice = useMemo(() => {
    if (!strikesSorted.length) return [];
    const idx = strikesSorted.findIndex((row) => String(row.strike) === String(nearestSpotStrike));
    const center = idx >= 0 ? idx : Math.floor(strikesSorted.length / 2);
    const start = Math.max(0, center - 3);
    const end = Math.min(strikesSorted.length, start + 8);
    return strikesSorted.slice(start, end);
  }, [strikesSorted, nearestSpotStrike]);

  const supportStrike = useMemo(() => {
    let best = null as SummaryRow | null;
    displayRows.forEach((row) => {
      if (!best || row.PE_OI > best.PE_OI) best = row;
    });
    return best?.strike ?? null;
  }, [displayRows]);

  const resistanceStrike = useMemo(() => {
    let best = null as SummaryRow | null;
    displayRows.forEach((row) => {
      if (!best || row.CE_OI > best.CE_OI) best = row;
    });
    return best?.strike ?? null;
  }, [displayRows]);

  const maxVolumeStrike = useMemo(() => {
    let best = null as SummaryRow | null;
    let bestVol = -1;
    displayRows.forEach((row) => {
      const vol = (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0);
      if (vol > bestVol) {
        bestVol = vol;
        best = row;
      }
    });
    return best?.strike ?? null;
  }, [displayRows]);

  const callMiniOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { left: 36, right: 28, top: 28, bottom: 36 },
      xAxis: { type: "category", data: displayStrikes, axisLabel: { color: "#c7cbd4" } },
      yAxis: [{ type: "value", axisLabel: { color: "#c7cbd4" } }, { type: "value", axisLabel: { color: "#c7cbd4" } }],
      series: [
        { name: "Call OI", type: "bar", data: displayCeOi, itemStyle: { color: "#2f6bd2" } },
        { name: "Call Volume", type: "line", yAxisIndex: 1, data: displayCeVol, smooth: true, lineStyle: { color: "#e6e6e6", width: 2 }, itemStyle: { color: "#e6e6e6" } },
      ],
    }),
    [displayStrikes, displayCeOi, displayCeVol]
  );

  const putMiniOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { left: 36, right: 28, top: 28, bottom: 36 },
      xAxis: { type: "category", data: displayStrikes, axisLabel: { color: "#c7cbd4" } },
      yAxis: [{ type: "value", axisLabel: { color: "#c7cbd4" } }, { type: "value", axisLabel: { color: "#c7cbd4" } }],
      series: [
        { name: "Put OI", type: "bar", data: displayPeOi, itemStyle: { color: "#4a9a67" } },
        { name: "Put Volume", type: "line", yAxisIndex: 1, data: displayPeVol, smooth: true, lineStyle: { color: "#b7f5cf", width: 2 }, itemStyle: { color: "#b7f5cf" } },
      ],
    }),
    [displayStrikes, displayPeOi, displayPeVol]
  );

  const highlight = useMemo(() => {
    const pickThreshold = (values: number[]) => {
      const sorted = [...values].sort((a, b) => b - a);
      if (sorted.length === 0) return null;
      return sorted[Math.min(2, sorted.length - 1)];
    };

    const ceOiValues: number[] = [];
    const peOiValues: number[] = [];
    const volValues: number[] = [];

    displayRows.forEach((row) => {
      const ceOi = Number(row.CE_OI) || 0;
      const peOi = Number(row.PE_OI) || 0;
      const vol = (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0);
      ceOiValues.push(ceOi);
      peOiValues.push(peOi);
      volValues.push(vol);
    });

    return {
      ceOiThreshold: pickThreshold(ceOiValues),
      peOiThreshold: pickThreshold(peOiValues),
      volThreshold: pickThreshold(volValues),
    };
  }, [displayRows]);

  const volumeSorted = useMemo(() => {
    const vols = displayRows.map(
      (row) => (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0)
    );
    return [...vols].sort((a, b) => b - a);
  }, [displayRows]);
  const volumeSpikeThreshold = volumeSorted.length ? volumeSorted[Math.min(2, volumeSorted.length - 1)] : null;

  const alertItems = useMemo(() => {
    const alerts: string[] = [];
    const resRow = displayRows.find((row) => String(row.strike) === String(resistanceStrike));
    if (resRow && resRow.CE_DeltaOI < 0) {
      alerts.push(`CE OI Unwinding at ${formatNumber(resRow.strike)}`);
    }
    const supRow = displayRows.find((row) => String(row.strike) === String(supportStrike));
    if (supRow && supRow.PE_DeltaOI < 0) {
      alerts.push(`PE OI Unwinding at ${formatNumber(supRow.strike)}`);
    }
    const maxVolRow = displayRows.find((row) => String(row.strike) === String(maxVolumeStrike));
    if (maxVolRow && volumeSpikeThreshold !== null) {
      const vol = (Number(maxVolRow.CE_Volume) || 0) + (Number(maxVolRow.PE_Volume) || 0);
      if (vol >= volumeSpikeThreshold) {
        alerts.push(`Volume Spike at ${formatNumber(maxVolRow.strike)}`);
      }
    }
    if (resistanceStrike !== null) {
      alerts.push(`Possible Breakout Above ${formatNumber(resistanceStrike)}`);
    }
    if (!alerts.length) alerts.push("No major OI/Volume alerts");
    return alerts;
  }, [displayRows, resistanceStrike, supportStrike, maxVolumeStrike, volumeSpikeThreshold]);

  const intradayEngine = useMemo(() => {
    const parseMinutes = (text: string | null | undefined) => {
      if (!text) return null;
      const match = text.match(/(\d{1,2}):(\d{2})/);
      if (!match) return null;
      const hh = Number(match[1]);
      const mm = Number(match[2]);
      if (Number.isNaN(hh) || Number.isNaN(mm)) return null;
      return hh * 60 + mm;
    };

    const fallbackTime = new Date().toLocaleTimeString("en-IN", {
      timeZone: "Asia/Kolkata",
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
    });
    const minutes = parseMinutes(meta?.timestamp ?? null) ?? parseMinutes(fallbackTime);
    let sessionPhase = "Off session";
    if (minutes !== null) {
      if (minutes >= 9 * 60 + 15 && minutes < 10 * 60 + 30) sessionPhase = "Opening drive";
      else if (minutes >= 10 * 60 + 30 && minutes < 14 * 60 + 30) sessionPhase = "Midday balance";
      else if (minutes >= 14 * 60 + 30 && minutes <= 15 * 60 + 30) sessionPhase = "Closing move";
    }

    const sorted = [...displayRows].sort((a, b) => Number(a.strike) - Number(b.strike));
    const spot = typeof spotValue === "number" ? spotValue : null;

    const getLevels = (rows: SummaryRow[]) => {
      let support: number | null = null;
      let resistance: number | null = null;
      let maxPe = -1;
      let maxCe = -1;
      rows.forEach((row) => {
        const peOi = Number(row.PE_OI) || 0;
        const ceOi = Number(row.CE_OI) || 0;
        if (peOi > maxPe) {
          maxPe = peOi;
          support = Number(row.strike);
        }
        if (ceOi > maxCe) {
          maxCe = ceOi;
          resistance = Number(row.strike);
        }
      });
      return { support, resistance };
    };

    const strikeStep = sorted.length > 1 ? Math.abs(Number(sorted[1].strike) - Number(sorted[0].strike)) : 0;
    const shiftThreshold = strikeStep > 0 ? Math.max(1, Math.floor(strikeStep / 2)) : 1;
    const previous = history.length >= 2 ? history[history.length - 2] : null;
    const prevLevels = previous ? getLevels(previous.rows) : { support: null as number | null, resistance: null as number | null };
    const currLevels = getLevels(displayRows);
    const supportShift =
      prevLevels.support !== null && currLevels.support !== null
        ? currLevels.support - prevLevels.support
        : 0;
    const resistanceShift =
      prevLevels.resistance !== null && currLevels.resistance !== null
        ? currLevels.resistance - prevLevels.resistance
        : 0;

    const shiftLabel = (shift: number) => {
      if (shift > 0) return `up ${formatNumber(shift)}`;
      if (shift < 0) return `down ${formatNumber(Math.abs(shift))}`;
      return "flat";
    };

    const atmRow = displayRows.find((row) => String(row.strike) === String(nearestSpotStrike));
    const avgTotalVol =
      displayRows.length > 0
        ? displayRows.reduce(
            (acc, row) => acc + (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0),
            0
          ) / displayRows.length
        : 0;
    const atmVol = atmRow
      ? (Number(atmRow.CE_Volume) || 0) + (Number(atmRow.PE_Volume) || 0)
      : 0;

    const trapContext: TrapMarketContext | null =
      spot !== null && resistanceStrike !== null && supportStrike !== null
        ? {
            symbol,
            spot,
            resistance: Number(resistanceStrike),
            support: Number(supportStrike),
            strikes: sorted.map((row) => ({
              strike: Number(row.strike) || 0,
              ceOIChange: Number(row.CE_DeltaOI) || 0,
              peOIChange: Number(row.PE_DeltaOI) || 0,
              ceVolume: Number(row.CE_Volume) || 0,
              peVolume: Number(row.PE_Volume) || 0,
            })),
          }
        : null;
    const trap = trapContext
      ? detectTrap(trapContext)
      : {
          bullTrap: false,
          bearTrap: false,
          trapLikely: false,
          message: "No trap setup",
          trapScore: 0,
          trapRisk: "Safe breakout",
          weakParticipation: false,
          volumeExpansion: false,
        };
    const trapLikely = trap.trapLikely;
    const trapMessage = trap.message;
    const atmVolumeShock = avgTotalVol > 0 && atmVol > avgTotalVol * ATM_VOLUME_SHOCK_MULTIPLIER;
    const shortCoveringBurst =
      displayRows.filter(
        (row) =>
          ((row.CE_Interpretation || "").includes("Short Covering") ||
            (row.PE_Interpretation || "").includes("Short Covering")) &&
          ((row.CE_VolDir || "") === "↑" || (row.PE_VolDir || "") === "↑")
      ).length >= SHORT_COVERING_BURST_MIN_STRIKES;
    const newResistanceFormed = Math.abs(resistanceShift) >= shiftThreshold;

    const engineAlerts: string[] = [];
    if (newResistanceFormed && currLevels.resistance !== null) {
      engineAlerts.push(
        `New resistance formed at ${formatNumber(currLevels.resistance)} (shift ${shiftLabel(
          resistanceShift
        )})`
      );
    }
    if (shortCoveringBurst) {
      engineAlerts.push("Short covering burst detected across active strikes");
    }
    if (atmVolumeShock && nearestSpotStrike !== null) {
      engineAlerts.push(`ATM volume shock at ${formatNumber(nearestSpotStrike)}`);
    }
    if (trapLikely) {
      engineAlerts.push(trapMessage);
    }
    if (!engineAlerts.length) engineAlerts.push("No intraday trigger from decision engine");

    return {
      sessionPhase,
      trapLikely,
      trapMessage,
      trapScore: trap.trapScore,
      trapRisk: trap.trapRisk,
      weakParticipation: trap.weakParticipation,
      volumeExpansion: trap.volumeExpansion,
      supportShift,
      resistanceShift,
      shiftSummary: `Support ${shiftLabel(supportShift)} | Resistance ${shiftLabel(resistanceShift)}`,
      engineAlerts,
    };
  }, [meta?.timestamp, displayRows, nearestSpotStrike, spotValue, supportStrike, resistanceStrike, history, symbol]);

  const velocityByStrike = useMemo(() => {
    const prev = history.length >= 2 ? history[history.length - 2] : null;
    const curr = history.length >= 1 ? history[history.length - 1] : null;
    const output = new Map<
      string,
      {
        ceDoiPerMin: number;
        ceVolPerMin: number;
        peDoiPerMin: number;
        peVolPerMin: number;
      }
    >();
    if (!prev || !curr) return output;
    const elapsedMs = Math.max(1, curr.fetchedAtMs - prev.fetchedAtMs);
    const minutes = elapsedMs / 60000;
    const prevByStrike = new Map(prev.rows.map((row) => [String(row.strike), row] as const));
    curr.rows.forEach((row) => {
      const before = prevByStrike.get(String(row.strike));
      if (!before) return;
      output.set(String(row.strike), {
        ceDoiPerMin: ((Number(row.CE_OI) || 0) - (Number(before.CE_OI) || 0)) / minutes,
        ceVolPerMin: ((Number(row.CE_Volume) || 0) - (Number(before.CE_Volume) || 0)) / minutes,
        peDoiPerMin: ((Number(row.PE_OI) || 0) - (Number(before.PE_OI) || 0)) / minutes,
        peVolPerMin: ((Number(row.PE_Volume) || 0) - (Number(before.PE_Volume) || 0)) / minutes,
      });
    });
    return output;
  }, [history]);

  const combinedAlerts = useMemo(() => {
    const apiAlerts: UiAlert[] = (intelligence?.signals?.alerts ?? []).map((a) => ({
      message: a.message,
      type: a.type,
      severity: classifyAlertSeverity(a.message),
    }));
    const localAlerts: UiAlert[] = [...intradayEngine.engineAlerts, ...alertItems].map((msg) => ({
      message: msg,
      type: "primary",
      severity: classifyAlertSeverity(msg),
    }));
    const merged = [...apiAlerts, ...localAlerts];
    const deduped: UiAlert[] = [];
    const seen = new Set<string>();
    for (const item of merged) {
      const key = `${item.type}::${item.message}`;
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(item);
    }
    return deduped.slice(0, 8);
  }, [intelligence?.signals?.alerts, intradayEngine.engineAlerts, alertItems]);

  const maxMetrics = useMemo(() => {
    const max = (values: number[]) => (values.length ? Math.max(...values) : 1);
    return {
      ceOi: max(displayRows.map((row) => Number(row.CE_OI) || 0)),
      peOi: max(displayRows.map((row) => Number(row.PE_OI) || 0)),
      ceVol: max(displayRows.map((row) => Number(row.CE_Volume) || 0)),
      peVol: max(displayRows.map((row) => Number(row.PE_Volume) || 0)),
    };
  }, [displayRows]);

  const spotRow = useMemo(
    () => displayRows.find((row) => String(row.strike) === String(nearestSpotStrike)) ?? null,
    [displayRows, nearestSpotStrike]
  );



  const breakoutModel = useMemo(() => {
    const defaultModel = {
      upProbability: 50,
      downProbability: 50,
      signal: "Range likely",
      confidence: 50,
      factors: ["Insufficient scoring context"],
    };
    if (!displayRows.length) return defaultModel;

    const sorted = [...displayRows].sort((a, b) => Number(a.strike) - Number(b.strike));
    const atmIndex = sorted.findIndex((row) => String(row.strike) === String(nearestSpotStrike));
    const centerIdx = atmIndex >= 0 ? atmIndex : Math.floor(sorted.length / 2);
    const atmBand = sorted.slice(Math.max(0, centerIdx - ATM_BAND_RANGE), Math.min(sorted.length, centerIdx + ATM_BAND_RANGE + 1));

    const priceChange = indexRow?.percChange ?? 0;
    const atmPE_OI_change = atmBand.reduce((acc, row) => acc + (Number(row.PE_DeltaOI) || 0), 0);
    const atmCE_OI_change = atmBand.reduce((acc, row) => acc + (Number(row.CE_DeltaOI) || 0), 0);

    const globalAvgVolume =
      sorted.reduce((sum, s) => sum + (Number(s.CE_Volume) || 0) + (Number(s.PE_Volume) || 0), 0) /
      Math.max(1, sorted.length);
    const currentVolume =
      atmBand.reduce((sum, s) => sum + (Number(s.CE_Volume) || 0) + (Number(s.PE_Volume) || 0), 0) /
      Math.max(1, atmBand.length);
    const volumeExpansion = currentVolume > 1.3 * globalAvgVolume;

    const putOI = sorted.reduce((sum, s) => sum + (Number(s.PE_OI) || 0), 0);
    const callOI = sorted.reduce((sum, s) => sum + (Number(s.CE_OI) || 0), 0);

    const maxPut = [...sorted].sort((a, b) => (Number(b.PE_OI) || 0) - (Number(a.PE_OI) || 0))[0];
    const strikeStep = sorted.length > 1 ? Math.abs(Number(sorted[1].strike) - Number(sorted[0].strike)) : 50;
    const maxPutNearAtm =
      maxPut && nearestSpotStrike !== null
        ? Math.abs((Number(maxPut.strike) || 0) - Number(nearestSpotStrike)) <= strikeStep * 2
        : false;

    let bullishScore = 0;
    if (priceChange > 0) bullishScore += 20;
    if (atmPE_OI_change > 0 && atmCE_OI_change <= 0) bullishScore += 25;
    if (volumeExpansion) bullishScore += 20;
    if (putOI > callOI) bullishScore += 20;
    if (maxPutNearAtm) bullishScore += 15;
    bullishScore = Math.max(0, Math.min(100, bullishScore));

    const upProbability = bullishScore;
    const downProbability = 100 - bullishScore;
    const confidence = Math.max(upProbability, downProbability);
    const factors = [
      `Price momentum: ${priceChange > 0 ? "bullish" : priceChange < 0 ? "bearish" : "flat"}`,
      `ATM OI direction: PEΔ ${formatSigned(atmPE_OI_change)} / CEΔ ${formatSigned(atmCE_OI_change)}`,
      `Volume expansion: ${volumeExpansion ? "yes" : "no"} (ATM avg ${formatNumber(Math.round(currentVolume))})`,
    ];

    const signal =
      upProbability > 60
        ? `Breakout above ${formatNumber(resistanceStrike)} more likely`
        : downProbability > 60
          ? `Breakdown below ${formatNumber(supportStrike)} more likely`
          : "Range likely";

    return { upProbability, downProbability, signal, confidence, factors };
  }, [displayRows, nearestSpotStrike, supportStrike, resistanceStrike, indexRow?.percChange]);

  const autoTargetProjection = useMemo(() => {
    const sorted = [...displayRows]
      .map((row) => ({ ...row, strikeNum: Number(row.strike) }))
      .filter((row) => !Number.isNaN(row.strikeNum))
      .sort((a, b) => a.strikeNum - b.strikeNum);
    const spot = typeof spotValue === "number" ? spotValue : null;
    if (!sorted.length || spot === null || resistanceStrike === null || supportStrike === null) {
      return {
        breakoutUp: false,
        breakoutDown: false,
        target1: null as number | null,
        target2: null as number | null,
        accelerationMode: false,
        status: "No breakout",
      };
    }

    const bufferPct = getBreakBufferPct(symbol);
    const breakBuffer = (spot * bufferPct) / 100;
    const breakoutUp = spot > Number(resistanceStrike) + breakBuffer;
    const breakoutDown = spot < Number(supportStrike) - breakBuffer;
    const avgStrikeOI =
      sorted.reduce(
        (sum, row) => sum + (Number(row.CE_OI) || 0) + (Number(row.PE_OI) || 0),
        0
      ) / Math.max(1, sorted.length);

    let target1: number | null = null;
    let target2: number | null = null;
    let accelerationMode = false;

    if (breakoutUp) {
      const nextCall = sorted
        .filter((row) => row.strikeNum > Number(resistanceStrike))
        .sort((a, b) => (Number(b.CE_OI) || 0) - (Number(a.CE_OI) || 0))[0];
      if (nextCall) {
        target1 = nextCall.strikeNum;
        target2 = target1 + (target1 - Number(resistanceStrike));
        const nextTwo = sorted
          .filter((row) => row.strikeNum > Number(resistanceStrike))
          .slice(0, 2);
        if (
          nextTwo.length === 2 &&
          nextTwo.every(
            (row) => (Number(row.CE_OI) || 0) + (Number(row.PE_OI) || 0) < 0.5 * avgStrikeOI
          )
        ) {
          accelerationMode = true;
          target2 = target1 + 1.5 * (target2 - target1);
        }
      }
    } else if (breakoutDown) {
      const nextPut = sorted
        .filter((row) => row.strikeNum < Number(supportStrike))
        .sort((a, b) => (Number(b.PE_OI) || 0) - (Number(a.PE_OI) || 0))[0];
      if (nextPut) {
        target1 = nextPut.strikeNum;
        target2 = target1 - (Number(supportStrike) - target1);
        const nextTwo = sorted
          .filter((row) => row.strikeNum < Number(supportStrike))
          .slice(-2);
        if (
          nextTwo.length === 2 &&
          nextTwo.every(
            (row) => (Number(row.CE_OI) || 0) + (Number(row.PE_OI) || 0) < 0.5 * avgStrikeOI
          )
        ) {
          accelerationMode = true;
          target2 = target1 - 1.5 * (target1 - target2);
        }
      }
    }

    const status = breakoutUp
      ? "Breakout up confirmed"
      : breakoutDown
        ? "Breakout down confirmed"
        : "No breakout";
    return { breakoutUp, breakoutDown, target1, target2, accelerationMode, status };
  }, [displayRows, spotValue, resistanceStrike, supportStrike, symbol]);

  const effectiveTargetProjection = useMemo(() => {
    if (apiTargetProjection) {
      return {
        target1: apiTargetProjection.targetPrimary,
        target2: apiTargetProjection.targetSecondary,
        status:
          apiTargetProjection.state === "BREAKOUT_UP"
            ? "Breakout up confirmed"
            : apiTargetProjection.state === "BREAKOUT_DOWN"
              ? "Breakout down confirmed"
              : "No breakout",
        direction: apiTargetProjection.direction,
        note: apiTargetProjection.targetNote,
      };
    }
    return {
      target1: autoTargetProjection.target1,
      target2: autoTargetProjection.target2,
      status: autoTargetProjection.status,
      direction: null as string | null,
      note: null as string | null,
    };
  }, [apiTargetProjection, autoTargetProjection]);

  const scalpingEngine = useMemo(() => {
    const sorted = [...displayRows]
      .map((row) => ({ ...row, strikeNum: Number(row.strike) }))
      .filter((row) => !Number.isNaN(row.strikeNum))
      .sort((a, b) => a.strikeNum - b.strikeNum);
    const spot = typeof spotValue === "number" ? spotValue : null;
    if (!sorted.length || spot === null) {
      return {
        momentumScore: 0,
        vwapBias: "Unavailable",
        quickTarget: null as number | null,
        reversalRisk: 0,
        fastMove: false,
        exitSignal: false,
      };
    }

    const atmIndex = sorted.findIndex((row) => String(row.strike) === String(nearestSpotStrike));
    const center = atmIndex >= 0 ? atmIndex : Math.floor(sorted.length / 2);
    const band = sorted.slice(Math.max(0, center - 3), Math.min(sorted.length, center + 4));
    const atm = sorted[Math.max(0, center)];

    const priceChange = indexRow?.percChange ?? 0;
    const globalAvgVol =
      sorted.reduce((sum, row) => sum + (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0), 0) /
      Math.max(1, sorted.length);
    const bandAvgVol =
      band.reduce((sum, row) => sum + (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0), 0) /
      Math.max(1, band.length);
    const volumeExpansion = bandAvgVol > 1.5 * globalAvgVol;
    const directionalOI =
      ((Number(atm.PE_DeltaOI) || 0) > 0 && (Number(atm.CE_DeltaOI) || 0) <= 0) ||
      ((Number(atm.CE_DeltaOI) || 0) > 0 && (Number(atm.PE_DeltaOI) || 0) <= 0);
    const fastMove = Math.abs(priceChange) > 0.25 && volumeExpansion && directionalOI;

    const avgSpot =
      history.length > 0
        ? history
            .map((h) => (typeof h.spot === "number" ? h.spot : null))
            .filter((v): v is number => v !== null)
            .reduce((a, b) => a + b, 0) /
          Math.max(
            1,
            history
              .map((h) => (typeof h.spot === "number" ? h.spot : null))
              .filter((v): v is number => v !== null).length
          )
        : spot;
    const vwapBias = spot > avgSpot ? "Above VWAP" : spot < avgSpot ? "Below VWAP" : "At VWAP";

    const bullishSetup =
      vwapBias === "Above VWAP" &&
      (Number(atm.PE_DeltaOI) || 0) > 0 &&
      (Number(atm.CE_DeltaOI) || 0) <= 0 &&
      volumeExpansion;
    const bearishSetup =
      vwapBias === "Below VWAP" &&
      (Number(atm.CE_DeltaOI) || 0) > 0 &&
      (Number(atm.PE_DeltaOI) || 0) <= 0 &&
      volumeExpansion;

    let quickTarget: number | null = null;
    if (bullishSetup && center < sorted.length - 1) quickTarget = sorted[center + 1].strikeNum;
    if (bearishSetup && center > 0) quickTarget = sorted[center - 1].strikeNum;

    const prev = history.length >= 2 ? history[history.length - 2] : null;
    const prevBandVol =
      prev && band.length
        ? band.reduce((sum, row) => {
            const r = prev.rows.find((x) => String(x.strike) === String(row.strike));
            return sum + ((r ? Number(r.CE_Volume) || 0 : 0) + (r ? Number(r.PE_Volume) || 0 : 0));
          }, 0)
        : bandAvgVol;
    const currBandVol = band.reduce(
      (sum, row) => sum + (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0),
      0
    );
    const volumeDrops = prevBandVol > 0 ? currBandVol < prevBandVol * 0.9 : false;
    const oiStopsIncreasing =
      bullishSetup
        ? (Number(atm.PE_DeltaOI) || 0) <= 0
        : bearishSetup
          ? (Number(atm.CE_DeltaOI) || 0) <= 0
          : Math.abs(Number(atm.CE_DeltaOI) || 0) + Math.abs(Number(atm.PE_DeltaOI) || 0) < 1;
    const exitSignal = volumeDrops && oiStopsIncreasing;

    let momentumScore = 0;
    if (Math.abs(priceChange) > 0.25) momentumScore += 30;
    if (volumeExpansion) momentumScore += 30;
    if (directionalOI) momentumScore += 25;
    if (bullishSetup || bearishSetup) momentumScore += 15;
    momentumScore = Math.max(0, Math.min(100, momentumScore));

    const reversalRisk = Math.max(
      0,
      Math.min(
        100,
        (intradayEngine?.trapScore ?? 0) * 0.6 + (volumeDrops ? 20 : 0) + (!directionalOI ? 20 : 0)
      )
    );

    return {
      momentumScore,
      vwapBias,
      quickTarget,
      reversalRisk: Math.round(reversalRisk),
      fastMove,
      exitSignal,
    };
  }, [displayRows, spotValue, nearestSpotStrike, indexRow?.percChange, history, intradayEngine?.trapScore]);

  const smartMoneyZones = useMemo(() => {
    if (!displayRows.length) return { institutional: [] as number[], acceleration: [] as string[] };
    const sorted = [...displayRows].sort((a, b) => Number(a.strike) - Number(b.strike));
    const totalOi = sorted.map((row) => (Number(row.CE_OI) || 0) + (Number(row.PE_OI) || 0));
    const avgOi = totalOi.reduce((a, b) => a + b, 0) / Math.max(1, totalOi.length);
    const institutional = sorted
      .filter((row) => (Number(row.CE_OI) || 0) + (Number(row.PE_OI) || 0) > 2 * avgOi)
      .map((row) => Number(row.strike))
      .slice(0, 3);

    const lowThreshold = avgOi * 0.6;
    const acceleration: string[] = [];
    for (let i = 0; i < sorted.length - 2; i += 1) {
      const a = (Number(sorted[i].CE_OI) || 0) + (Number(sorted[i].PE_OI) || 0);
      const b = (Number(sorted[i + 1].CE_OI) || 0) + (Number(sorted[i + 1].PE_OI) || 0);
      const c = (Number(sorted[i + 2].CE_OI) || 0) + (Number(sorted[i + 2].PE_OI) || 0);
      if (a < lowThreshold && b < lowThreshold && c < lowThreshold) {
        acceleration.push(`${formatNumber(sorted[i].strike)}-${formatNumber(sorted[i + 2].strike)}`);
      }
    }
    return { institutional, acceleration: acceleration.slice(0, 2) };
  }, [displayRows]);

  const probabilityBias = useMemo(() => {
    let label: "Bullish" | "Bearish" | "Neutral" = "Neutral";
    if (breakoutModel.upProbability > 60) {
      label = "Bullish";
    } else if (breakoutModel.downProbability > 60) {
      label = "Bearish";
    }
    const confidence =
      breakoutModel.confidence >= 80
        ? "High"
        : breakoutModel.confidence >= 60
          ? "Medium"
          : "Low";
    return { label, confidence };
  }, [breakoutModel]);

  const displayBias = intelligence?.market_state?.bias ?? probabilityBias.label;
  const displayPrimaryBias = intelligence?.market_state?.primary_bias ?? displayBias;
  const displayDecisionState = intelligence?.market_state?.state ?? "Balanced / Wait";
  const displayBullProbability = intelligence?.market_state?.probability_bull ?? breakoutModel.upProbability;
  const displayBearProbability = intelligence?.market_state?.probability_bear ?? breakoutModel.downProbability;
  const displayConfidence = intelligence?.market_state?.confidence ?? breakoutModel.confidence;
  const displayTrapRiskPct = intelligence?.market_state?.trap_risk ?? intradayEngine.trapScore;
  const displayReversalRisk = intelligence?.market_state?.reversal_risk ?? scalpingEngine.reversalRisk;
  const adaptiveMode = intelligence?.market_state?.adaptive_mode ?? "Base";
  const adaptiveWeights = intelligence?.market_state?.adaptive_weights;
  const displayAlignmentCount = Math.max(
    0,
    Math.min(4, Math.round(((intelligence?.market_state?.alignment_ratio ?? (displayConfidence / 100)) || 0) * 4))
  );
  const displayVolatilityState = intelligence?.market_state?.volatility_state ?? "Stable";
  const displayFreshnessState = intelligence?.market_state?.freshness_state;
  const isExpiryMode = intelligence?.signals?.expiry_adaptive?.expiry_mode ?? false;
  const bannerLiveStatus: "live" | "stale" | "delayed" | "blocked" | "checking" =
    nseStatus === "blocked"
      ? "blocked"
      : nseStatus === "checking"
        ? "checking"
        : displayFreshnessState ?? "live";
  const displayTrapLevel =
    intelligence?.signals?.trap?.trap_level ??
    (displayTrapRiskPct > 65 ? "High" : displayTrapRiskPct > 45 ? "Moderate" : "Low");
  const rawTrapType = intelligence?.signals?.trap?.trap_type;
  const displayTrapType = rawTrapType ?? "No active trap";
  const showTrapAffectedLevel = intelligence?.signals?.trap?.show_affected_level ?? (rawTrapType !== null && rawTrapType !== undefined);
  const displaySupport = intelligence?.market_state?.support ?? supportStrike;
  const displayResistance = intelligence?.market_state?.resistance ?? resistanceStrike;
  const supportRangeRaw = intelligence?.levels?.support?.range;
  const resistanceRangeRaw = intelligence?.levels?.resistance?.range;
  const supportRangeText =
    Array.isArray(supportRangeRaw) && supportRangeRaw.length === 2
      ? `${formatNumber(supportRangeRaw[0] ?? null)}-${formatNumber(supportRangeRaw[1] ?? null)}`
      : "";
  const resistanceRangeText =
    Array.isArray(resistanceRangeRaw) && resistanceRangeRaw.length === 2
      ? `${formatNumber(resistanceRangeRaw[0] ?? null)}-${formatNumber(resistanceRangeRaw[1] ?? null)}`
      : "";
  const supportPressureText =
    intelligence?.levels?.support?.zone_state ??
    intelligence?.market_state?.support_zone_state ??
    undefined;
  const resistancePressureText =
    intelligence?.levels?.resistance?.zone_state ??
    intelligence?.market_state?.resistance_zone_state ??
    undefined;
  const displayDecisionText = buildDecisionSummary(
    displayBias,
    displaySupport,
    displayResistance,
    intelligence?.market_state?.summary_line ?? breakoutModel.signal
  );
  const displayTarget1 = intelligence?.market_state?.target1 ?? effectiveTargetProjection.target1;
  const displayTarget2 = intelligence?.market_state?.target2 ?? effectiveTargetProjection.target2;
  const momentumExhaustion = intelligence?.signals?.momentum_exhaustion;
  const showMomentumExhaustion = momentumExhaustion?.momentum_exhaustion ?? false;
  const momentumExhaustionMessage =
    momentumExhaustion?.exhaustion_type === "Bullish Exhaustion"
      ? "⚠ Bullish Exhaustion — Upside momentum weakening"
      : momentumExhaustion?.exhaustion_type === "Bearish Exhaustion"
        ? "⚠ Bearish Exhaustion — Downside losing strength"
        : "";
  const autoExitSignal = intelligence?.signals?.auto_exit?.exit_signal ?? false;
  const autoExitMessage =
    displayReversalRisk > 60
      ? "🔔 High Reversal Risk — Protect Profits"
      : "🔔 Consider Partial Exit — Momentum Weakening";
  const tradePlan = intelligence?.trade_plan;
  const displayTradePlan = {
    strategy_type: tradePlan?.strategy_type ?? "Balanced / Selective",
    entry_zone: tradePlan?.entry_zone ?? "Wait for confirmation near key levels.",
    stop_hint: tradePlan?.stop_hint ?? "Use defined risk beyond nearby structure.",
    target_primary: tradePlan?.target_primary ?? displayTarget1,
    target_extended: tradePlan?.target_extended ?? displayTarget2,
    caution_note: tradePlan?.caution_note ?? "Keep size controlled when signals are mixed.",
  };
  const playbook = intelligence?.intraday_playbook;
  const structureScore = Number(intelligence?.market_state?.market_structure_score ?? 0);
  const structureState = intelligence?.market_state?.structure_state ?? "-";
  const driftState = intelligence?.market_state?.drift ?? "Stable";
  const projectionState = intelligence?.market_state?.projection ?? "No Confirmed Breakout";
  const conflictState = intelligence?.market_state?.conflict_market_state ?? "Balanced";
  const directionalForceBullRaw = Number(
    intelligence?.market_state?.directional_force?.bull ?? displayBullProbability ?? 50
  );
  const directionalForceBull = directionalForceBullRaw > 1 ? directionalForceBullRaw / 100 : directionalForceBullRaw;
  const alignmentScoreRaw = Number(intelligence?.signals?.alignment_filter?.alignment_score ?? 0);
  const alignmentScore = alignmentScoreRaw > 1 ? alignmentScoreRaw / 100 : alignmentScoreRaw;
  const oiVelocityScoreRaw = Number(intelligence?.signals?.oi?.oi_velocity_score ?? 0);
  const oiVelocityScore = oiVelocityScoreRaw > 1 ? oiVelocityScoreRaw / 100 : oiVelocityScoreRaw;
  const breakoutStrengthRaw = Number(intelligence?.signals?.breakout?.breakout_strength ?? 0);
  const breakoutStrength = breakoutStrengthRaw > 1 ? breakoutStrengthRaw / 100 : breakoutStrengthRaw;
  const trapProbabilityRaw = Number(displayTrapRiskPct ?? 0);
  const trapProbability = trapProbabilityRaw > 1 ? trapProbabilityRaw / 100 : trapProbabilityRaw;
  const pressureRawScore = Math.max(
    0,
    Math.min(
      100,
      ((0.35 * directionalForceBull +
        0.25 * alignmentScore +
        0.2 * oiVelocityScore +
        0.1 * breakoutStrength -
        0.2 * trapProbability) *
        100)
    )
  );
  const pressureStateLabel =
    pressureSmoothed < 35
      ? "Sell Pressure"
      : pressureSmoothed < 55
        ? "Balanced"
        : pressureSmoothed < 75
          ? "Buy Pressure"
          : "Strong Buy Pressure";
  const clarityRaw = Number(intelligence?.market_state?.clarity ?? displayConfidence ?? 0);
  const clarityNorm = clarityRaw > 1 ? clarityRaw / 100 : clarityRaw;
  const readinessRaw = Math.max(
    0,
    Math.min(
      100,
      ((0.3 * alignmentScore +
        0.25 * clarityNorm +
        0.2 * breakoutStrength +
        0.15 * oiVelocityScore -
        0.25 * trapProbability) *
        100)
    )
  );
  const readinessCandidate: "WAIT" | "CAUTION" | "READY" =
    readinessRaw < 40 ? "WAIT" : readinessRaw < 65 ? "CAUTION" : "READY";
  const playbookPlan = playbook?.strategy ?? displayTradePlan.strategy_type;
  const supportZoneText = Array.isArray(playbook?.support_zone)
    ? `${formatNumber(playbook?.support_zone[0] ?? null)} - ${formatNumber(playbook?.support_zone[1] ?? null)}`
    : formatNumber(displaySupport);
  const resistanceZoneText = Array.isArray(playbook?.resistance_zone)
    ? `${formatNumber(playbook?.resistance_zone[0] ?? null)} - ${formatNumber(playbook?.resistance_zone[1] ?? null)}`
    : formatNumber(displayResistance);
  const projectedMovePts =
    Number(apiTargetProjection?.projectedMove ?? 0) > 0
      ? Number(apiTargetProjection?.projectedMove)
      : Math.max(50, Math.abs(Number(displayTarget1 ?? 0) - Number(displayResistance ?? 0)));
  const breakAbovePrimary = Number(displayResistance ?? 0) + projectedMovePts * 0.6;
  const breakAboveExtended = Number(displayResistance ?? 0) + projectedMovePts * 1.0;
  const breakBelowPrimary = Number(displaySupport ?? 0) - projectedMovePts * 0.6;
  const breakBelowExtended = Number(displaySupport ?? 0) - projectedMovePts * 1.0;
  const trapSuggestedAction =
    displayTrapLevel === "High"
      ? "Avoid fresh breakout entries. Wait for re-test confirmation with stronger ATM participation."
      : displayTrapLevel === "Moderate"
        ? "Reduce size and wait for one more confirmation candle."
        : "Trap risk low. Follow primary setup with normal risk controls.";

  useEffect(() => {
    const updateIfStable = (
      key: "structure" | "pressure" | "trap",
      nextValue: string
    ) => {
      const pending = pendingBadgeRef.current[key];
      if (pending.value !== nextValue) {
        pendingBadgeRef.current[key] = { value: nextValue, count: 1 };
        return;
      }
      pending.count += 1;
      if (pending.count >= 2) {
        setStableBadges((prev) => (prev[key] === nextValue ? prev : { ...prev, [key]: nextValue }));
      }
    };

    updateIfStable("structure", structureState || "-");
    updateIfStable("pressure", driftState || "Stable");
    updateIfStable("trap", String(displayTrapLevel || "Low"));
  }, [structureState, driftState, displayTrapLevel]);

  useEffect(() => {
    setPressureSmoothed((prev) => (0.7 * prev) + (0.3 * pressureRawScore));
  }, [pressureRawScore]);

  useEffect(() => {
    const pending = readinessPendingRef.current;
    const rounded = Math.round(readinessRaw);
    if (pending.state !== readinessCandidate) {
      readinessPendingRef.current = { state: readinessCandidate, score: rounded, count: 1 };
      return;
    }
    pending.count += 1;
    pending.score = rounded;
    if (pending.count >= 2) {
      setReadinessDisplay({ state: readinessCandidate, score: rounded });
    }
  }, [readinessCandidate, readinessRaw]);

  const filteredAlerts = useMemo(() => {
    if (!MARKETING_MODE) return combinedAlerts;
    const suppressBreakout =
      displayVolatilityState === "Stable" ||
      String(effectiveTargetProjection.status || "").toLowerCase() === "no breakout";
    const filtered = combinedAlerts.filter((item) => {
      if (item.severity === "info") return false;
      const lower = item.message.toLowerCase();
      if (suppressBreakout && (lower.includes("breakout") || lower.includes("breakdown"))) {
        return false;
      }
      return true;
    });
    return filtered;
  }, [combinedAlerts, displayVolatilityState, effectiveTargetProjection.status]);

  const prioritizedAlerts = useMemo(() => {
    return [...filteredAlerts].sort((a, b) => {
      const pa = alertPriority(a);
      const pb = alertPriority(b);
      if (pa !== pb) return pa - pb;
      const sevRank = (x: UiAlert) => (x.severity === "high" ? 0 : x.severity === "watch" ? 1 : 2);
      return sevRank(a) - sevRank(b);
    });
  }, [filteredAlerts]);

  const visibleAlerts = prioritizedAlerts.slice(0, 2);
  const hiddenAlerts = showMoreAlerts ? prioritizedAlerts.slice(2) : [];
  const hiddenAlertCount = Math.max(0, prioritizedAlerts.length - 2);

  const visibleTabs: Array<
    "overview" | "charts" | "heatmap" | "writers" | "basis" | "option-chain" | "engine-health"
  > = MARKETING_MODE
    ? ["overview", "charts", "option-chain"]
    : ["overview", "charts", "heatmap", "writers", "basis", "option-chain", "engine-health"];

  useEffect(() => {
    if (!visibleTabs.includes(activeTab)) {
      setActiveTab("overview");
    }
  }, [activeTab, visibleTabs]);

  useEffect(() => {
    setShowMoreAlerts(false);
  }, [prioritizedAlerts.length]);

  const topWriters = useMemo(() => {
    if (!displayRows.length) {
      return { ce: [] as Array<{ strike: number; doi: number; volume: number; score: number }>, pe: [] as Array<{ strike: number; doi: number; volume: number; score: number }> };
    }
    const cePosDoi = displayRows.map((row) => Math.max(0, Number(row.CE_DeltaOI) || 0));
    const pePosDoi = displayRows.map((row) => Math.max(0, Number(row.PE_DeltaOI) || 0));
    const ceVols = displayRows.map((row) => Number(row.CE_Volume) || 0);
    const peVols = displayRows.map((row) => Number(row.PE_Volume) || 0);
    const quantile = (values: number[], q: number) => {
      const sorted = [...values].sort((a, b) => a - b);
      if (!sorted.length) return 0;
      const idx = Math.max(0, Math.min(sorted.length - 1, Math.floor(q * (sorted.length - 1))));
      return sorted[idx];
    };
    const ceDoiTh = quantile(cePosDoi, 0.8);
    const peDoiTh = quantile(pePosDoi, 0.8);
    const ceVolTh = quantile(ceVols, 0.8);
    const peVolTh = quantile(peVols, 0.8);

    const ce = displayRows
      .map((row) => {
        const doi = Math.max(0, Number(row.CE_DeltaOI) || 0);
        const volume = Number(row.CE_Volume) || 0;
        const score = doi * 0.6 + volume * 0.4;
        return { strike: row.strike, doi, volume, score };
      })
      .filter((x) => x.doi >= ceDoiTh && x.volume >= ceVolTh && x.doi > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    const pe = displayRows
      .map((row) => {
        const doi = Math.max(0, Number(row.PE_DeltaOI) || 0);
        const volume = Number(row.PE_Volume) || 0;
        const score = doi * 0.6 + volume * 0.4;
        return { strike: row.strike, doi, volume, score };
      })
      .filter((x) => x.doi >= peDoiTh && x.volume >= peVolTh && x.doi > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    return { ce, pe };
  }, [displayRows]);

  const futuresBasis = useMemo(() => {
    const spot = typeof spotValue === "number" ? spotValue : null;
    if (spot === null || nearestSpotStrike === null) {
      return {
        syntheticFuture: null as number | null,
        basis: null as number | null,
        basisPct: null as number | null,
        basisType: "Unavailable",
        direction: "No confirmation",
        method: "Synthetic ATM parity",
      };
    }
    const atm = displayRows.find((row) => String(row.strike) === String(nearestSpotStrike));
    if (!atm || atm.CE_LastPrice === undefined || atm.PE_LastPrice === undefined) {
      return {
        syntheticFuture: null as number | null,
        basis: null as number | null,
        basisPct: null as number | null,
        basisType: "Unavailable",
        direction: "No confirmation",
        method: "Synthetic ATM parity",
      };
    }
    const strike = Number(atm.strike) || 0;
    const ce = Number(atm.CE_LastPrice) || 0;
    const pe = Number(atm.PE_LastPrice) || 0;
    const syntheticFuture = strike + ce - pe;
    const basis = syntheticFuture - spot;
    const basisPct = spot !== 0 ? (basis / spot) * 100 : 0;
    const basisType = basis > 0 ? "Premium" : basis < 0 ? "Discount" : "Flat";
    const direction =
      basis > 0.08 * spot / 100
        ? "Bullish confirmation"
        : basis < -0.08 * spot / 100
          ? "Bearish confirmation"
          : "Neutral confirmation";
    return { syntheticFuture, basis, basisPct, basisType, direction, method: "Synthetic ATM parity" };
  }, [displayRows, nearestSpotStrike, spotValue]);

  const heatmapOption = useMemo(() => {
    const recent = [...history]
      .sort((a, b) => a.fetchedAtMs - b.fetchedAtMs)
      .slice(-120);
    if (recent.length < 2 || !displayRows.length) return null;
    const xLabels = recent.map((point) =>
      new Date(point.fetchedAtMs).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    );
    const strikeLabels = [...displayRows]
      .map((row) => Number(row.strike))
      .filter((value) => !Number.isNaN(value))
      .sort((a, b) => b - a)
      .map(String);
    const strikeSet = new Set(strikeLabels);

    const points: Array<[number, number, number]> = [];
    recent.forEach((snap, xIdx) => {
      const prevSnap = xIdx > 0 ? recent[xIdx - 1] : null;
      const prevRowsByStrike = new Map(
        (prevSnap?.rows ?? []).map((row) => [String(row.strike), row] as const)
      );
      const currentTotals = snap.rows.map(
        (row) => (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0)
      );
      const maxCurrentVol = Math.max(1, ...currentTotals);
      const minuteVolDeltas = snap.rows.map((row) => {
        const prev = prevRowsByStrike.get(String(row.strike));
        const currVol = (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0);
        const prevVol = prev ? (Number(prev.CE_Volume) || 0) + (Number(prev.PE_Volume) || 0) : 0;
        return Math.max(0, currVol - prevVol);
      });
      const maxVolDelta = Math.max(1, ...minuteVolDeltas);
      const rowsByStrike = new Map(
        snap.rows.map((row) => [String(row.strike), row] as const)
      );
      strikeLabels.forEach((strike, yIdx) => {
        if (!strikeSet.has(strike)) return;
        const row = rowsByStrike.get(strike);
        const prev = prevRowsByStrike.get(strike);
        if (!row) {
          points.push([xIdx, yIdx, 0]);
          return;
        }
        if (!prev) {
          points.push([xIdx, yIdx, 0]);
          return;
        }
        const ceOiDelta = (Number(row.CE_OI) || 0) - (Number(prev.CE_OI) || 0);
        const peOiDelta = (Number(row.PE_OI) || 0) - (Number(prev.PE_OI) || 0);
        const currVol = (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0);
        const prevVol = (Number(prev.CE_Volume) || 0) + (Number(prev.PE_Volume) || 0);
        const volDelta = Math.max(0, currVol - prevVol);
        const volFactor = volDelta / maxVolDelta;
        const directional =
          ((peOiDelta - ceOiDelta) / (Math.abs(peOiDelta) + Math.abs(ceOiDelta) + 1)) * 100;
        const pressureNow =
          (((Number(row.PE_DeltaOI) || 0) - (Number(row.CE_DeltaOI) || 0)) /
            (Math.abs(Number(row.PE_DeltaOI) || 0) + Math.abs(Number(row.CE_DeltaOI) || 0) + 1)) *
          100;
        const currentVolFactor = currVol / maxCurrentVol;
        let rawValue = directional * volFactor;
        if (Math.abs(rawValue) < 2) {
          // Fallback keeps heatmap visible when minute deltas are tiny.
          rawValue = pressureNow * (0.35 + 0.65 * currentVolFactor);
        }
        // Contrast boost: lifts low/mid values without blowing up large values.
        const enhanced = Math.sign(rawValue) * Math.pow(Math.abs(rawValue), 0.78);
        points.push([xIdx, yIdx, Number(enhanced.toFixed(2))]);
      });
    });
    const absValues = points.map((point) => Math.abs(point[2])).sort((a, b) => a - b);
    const p95Index = Math.max(0, Math.floor(absValues.length * 0.95) - 1);
    const maxAbs = Math.max(6, absValues[p95Index] ?? 6);

    return {
      tooltip: {
        position: "top",
        formatter: (params: { value: [number, number, number] }) => {
          const [x, y, value] = params.value;
          const side = value >= 0 ? "Put pressure" : "Call pressure";
          return `${strikeLabels[y]} @ ${xLabels[x]}<br/>${side}: ${Math.abs(value).toFixed(1)}`;
        },
      },
      grid: { left: 70, right: 18, top: 26, bottom: 56 },
      xAxis: {
        type: "category",
        data: xLabels,
        axisLabel: { color: "#c7cbd4", interval: Math.max(0, Math.floor(xLabels.length / 8)) },
      },
      yAxis: {
        type: "category",
        data: strikeLabels,
        axisLabel: {
          color: "#c7cbd4",
          formatter: (value: string) => {
            if (nearestSpotStrike !== null && String(value) === String(nearestSpotStrike)) {
              return `{atm|${value}}`;
            }
            return value;
          },
          rich: {
            atm: {
              color: "#111",
              backgroundColor: "#f3b45a",
              borderRadius: 4,
              padding: [2, 6],
              fontWeight: 700,
            },
          },
        },
      },
      visualMap: {
        min: -maxAbs,
        max: maxAbs,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: 8,
        textStyle: { color: "#c7cbd4" },
        inRange: {
          color: ["#f0446a", "#5a2440", "#1f2d3a", "#20533b", "#34d37a"],
        },
      },
      series: [
        {
          name: "Minute OI+Volume change",
          type: "heatmap",
          data: points,
          progressive: 3000,
          emphasis: { itemStyle: { borderColor: "#fff", borderWidth: 1 } },
          markLine:
            nearestSpotStrike !== null
              ? {
                  silent: true,
                  symbol: "none",
                  lineStyle: {
                    color: "#f3b45a",
                    width: 2,
                    type: "dashed",
                  },
                  label: {
                    show: true,
                    formatter: `Spot ${nearestSpotStrike}`,
                    color: "#111",
                    backgroundColor: "#f3b45a",
                    borderRadius: 4,
                    padding: [2, 6],
                  },
                  data: [{ yAxis: String(nearestSpotStrike) }],
                }
              : undefined,
        },
      ],
    };
  }, [history, displayRows, nearestSpotStrike]);

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Intraday Dashboard</p>
          <img src="/optionlens-logo.svg" alt="OptionLens" className="brand-logo" />
          <p className="subhead">
            Live CE/PE open interest and volume across strikes. Auto refreshes every 15s.
          </p>
        </div>
        <div className="meta">
          <button type="button" className="upgrade-disabled" disabled>
            Upgrade to Pro (Soon)
          </button>
          <span className="pill">React</span>
          <span className="pill">ECharts</span>
          <span className="pill">FastAPI</span>
          <span className={`pill status-pill ${nseStatus}`}>
            NSE {nseStatus === "checking" ? "checking" : nseStatus}
          </span>
        </div>
      </header>

      <section className="panel">
        <div className="controls">
          <label className="field">
            <span>Symbol</span>
            <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
              {SYMBOLS.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Instrument</span>
            <select value={instrumentType} onChange={(event) => setInstrumentType(event.target.value)}>
              <option value="Indices">Indices</option>
            </select>
          </label>
          <label className="field">
            <span>Expiry</span>
            <select value={expiry} onChange={(event) => setExpiry(event.target.value)}>
              {expiries.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Range Around Spot</span>
            <input
              type="number"
              min={1}
              max={50}
              value={rangeCount}
              onChange={(event) => setRangeCount(Number(event.target.value))}
              disabled={!rangeEnabled}
            />
          </label>
          <label className="field inline">
            <input
              type="checkbox"
              checked={rangeEnabled}
              onChange={(event) => setRangeEnabled(event.target.checked)}
            />
            <span>Use range filter</span>
          </label>
          <label className="field inline">
            <input
              type="checkbox"
              checked={useSample}
              onChange={(event) => setUseSample(event.target.checked)}
            />
            <span>Use sample data</span>
          </label>
          <label className="field inline">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
            />
            <span>Auto refresh</span>
          </label>
          <button type="button" onClick={handleManualRefresh}>
            Refresh now
          </button>
        </div>

        <div className="status">
          {status}
          {nseStatus === "blocked" && nseMessage ? ` | NSE: ${LIVE_DATA_UNAVAILABLE_MSG}` : ""}
        </div>

        <MarketBanner
          indexName={indexNameMap[symbol] ?? symbol}
          spot={formatNumber(spotValue)}
          spotDelta={
            indexRow?.last !== undefined && indexRow?.previousClose !== undefined
              ? `${indexRow.last >= indexRow.previousClose ? "▲" : "▼"} ${Math.abs(indexRow.last - indexRow.previousClose).toFixed(1)}`
              : undefined
          }
          pctChange={indexRow?.percChange !== undefined ? `${indexRow.percChange.toFixed(2)}%` : "-"}
          volatilityState={displayVolatilityState}
          updatedAt={lastUpdated || meta?.timestamp || "-"}
          liveStatus={bannerLiveStatus}
          expiryMode={isExpiryMode}
          phase={intradayEngine.sessionPhase}
          projection={effectiveTargetProjection.status}
          showProjection={!MARKETING_MODE}
          trend={displayBias}
        />

        <RetailSummaryStrip
          bias={String(displayPrimaryBias ?? displayBias)}
          readiness={readinessDisplay.state}
          support={formatNumber(displaySupport)}
          resistance={formatNumber(displayResistance)}
          trapRiskLabel={`${displayTrapLevel} (${Math.round(Number(displayTrapRiskPct ?? 0))}%)`}
        />

        <div className="ia-section-gap">
          <MarketPlaybookCard
            bias={String(playbook?.bias ?? displayPrimaryBias)}
            regime={String(playbook?.regime ?? displayDecisionState)}
            plan={String(playbookPlan)}
            support={supportZoneText}
            resistance={resistanceZoneText}
            expansionTarget={formatNumber(playbook?.expansion_target ?? null)}
          />
        </div>

        <div className="ia-grid-3">
          <DecisionPanel
            bias={displayBias}
            regime={String(playbook?.regime ?? displayDecisionState)}
            bullProbability={displayBullProbability}
            bearProbability={displayBearProbability}
            confidence={displayConfidence}
            trapRisk={displayTrapRiskPct}
            reversalRisk={displayReversalRisk}
            summaryLine={displayDecisionText}
            alignmentCount={displayAlignmentCount}
            marketingMode={MARKETING_MODE}
            adaptiveMode={adaptiveMode}
            adaptiveOiWeight={adaptiveWeights?.oi}
            adaptiveBreakoutWeight={adaptiveWeights?.breakout}
            marketStructureScore={structureScore}
            structureState={structureState}
            structureBadge={stableBadges.structure}
            pressureBadge={stableBadges.pressure}
            trapBadge={stableBadges.trap}
            projection={projectionState}
            conflictState={conflictState}
            pressureScore={pressureSmoothed}
            pressureStateLabel={pressureStateLabel}
            readinessState={readinessDisplay.state}
            readinessScore={readinessDisplay.score}
          />
          <div className="ia-card-stack">
            <KeyLevelsCard
              support={formatNumber(displaySupport)}
              resistance={formatNumber(displayResistance)}
              target1={formatNumber(displayTarget1)}
              target2={formatNumber(displayTarget2)}
              supportRange={supportRangeText}
              resistanceRange={resistanceRangeText}
              supportPressure={supportPressureText}
              resistancePressure={resistancePressureText}
            />
            <ExpansionTargetsCard
              resistance={formatNumber(displayResistance)}
              support={formatNumber(displaySupport)}
              breakAbovePrimary={formatNumber(breakAbovePrimary)}
              breakAboveExtended={formatNumber(breakAboveExtended)}
              breakBelowPrimary={formatNumber(breakBelowPrimary)}
              breakBelowExtended={formatNumber(breakBelowExtended)}
            />
          </div>
          <div className="ia-card">
            <h3 className="ia-card-title">Trap</h3>
            <TrapCard
              trap_probability={displayTrapRiskPct}
              trap_level={displayTrapLevel}
              trap_type={displayTrapType ?? "-"}
              trap_zone={Number(displayResistance ?? displaySupport ?? nearestSpotStrike ?? 0)}
              suggested_action={trapSuggestedAction}
              show_affected_level={showTrapAffectedLevel}
            />
          </div>
        </div>

        {dailyPerformance ? (
          <div className="ia-section-gap">
            <div className={`ia-card ia-collapsible ${showDailyPerformance ? "" : "ia-collapsed"}`}>
              <div className="ia-card-title-row">
                <h3 className="ia-card-title">Daily Performance</h3>
                <button type="button" className="ia-detail-toggle" onClick={() => setShowDailyPerformance((prev) => !prev)}>
                  {showDailyPerformance ? "Hide Details" : "Show Details"}
                </button>
              </div>
              {showDailyPerformance ? (
                MARKETING_MODE ? (
                  dailyPerformance.total_signals_logged < 5 ? (
                    <div className="ia-kpi-label">Collecting session data...</div>
                  ) : (
                    <div className="ia-kpi-grid">
                      <div>
                        <div className="ia-kpi-label">Winning Signals</div>
                        <div className="ia-kpi-value">
                          {Math.round((dailyPerformance.bias_accuracy_percent / 100) * dailyPerformance.total_signals_logged)}/
                          {dailyPerformance.total_signals_logged}
                        </div>
                      </div>
                      <div>
                        <div className="ia-kpi-label">Avg Target Hit Rate</div>
                        <div className="ia-kpi-value">
                          {Math.round((dailyPerformance.bias_accuracy_percent + dailyPerformance.exit_accuracy_percent) / 2)}%
                        </div>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="ia-kpi-grid">
                    <div>
                      <div className="ia-kpi-label">Bias Accuracy</div>
                      <div className="ia-kpi-value">{Math.round(dailyPerformance.bias_accuracy_percent)}%</div>
                    </div>
                    <div>
                      <div className="ia-kpi-label">Trap Accuracy</div>
                      <div className="ia-kpi-value">{Math.round(dailyPerformance.trap_accuracy_percent)}%</div>
                    </div>
                    <div>
                      <div className="ia-kpi-label">Exit Accuracy</div>
                      <div className="ia-kpi-value">{Math.round(dailyPerformance.exit_accuracy_percent)}%</div>
                    </div>
                    <div>
                      <div className="ia-kpi-label">Signals Logged</div>
                      <div className="ia-kpi-value">{dailyPerformance.total_signals_logged}</div>
                    </div>
                  </div>
                )
              ) : null}
            </div>
          </div>
        ) : null}

        {showMomentumExhaustion ? (
          <div className="ia-section-gap">
            <div className="ia-card ia-exhaustion-alert">{momentumExhaustionMessage}</div>
          </div>
        ) : null}

        {autoExitSignal ? (
          <div className="ia-section-gap">
            <div className="ia-card ia-exit-alert">{autoExitMessage}</div>
          </div>
        ) : null}

        <div className="ia-section-gap">
          <div className={`ia-card ia-collapsible ${showTradePlan ? "" : "ia-collapsed"}`}>
            <div className="ia-card-title-row">
              <h3 className="ia-card-title">Trade Plan</h3>
              <button type="button" className="ia-detail-toggle" onClick={() => setShowTradePlan((prev) => !prev)}>
                {showTradePlan ? "Hide Details" : "Show Details"}
              </button>
            </div>
            {showTradePlan ? (
              <>
                <div className="ia-subtle-divider">How to Trade This Structure</div>
                <div className="ia-kpi-grid">
                  <div>
                    <div className="ia-kpi-label">Strategy</div>
                    <div className="ia-kpi-value">{displayTradePlan.strategy_type}</div>
                  </div>
                  <div>
                    <div className="ia-kpi-label">Primary Target</div>
                    <div className="ia-kpi-value">{formatNumber(displayTradePlan.target_primary)}</div>
                  </div>
                  {displayConfidence >= 40 ? (
                    <div>
                      <div className="ia-kpi-label">Extended Target</div>
                      <div className="ia-kpi-value">{formatNumber(displayTradePlan.target_extended)}</div>
                    </div>
                  ) : null}
                </div>
                <div className="ia-kpi-label" style={{ marginTop: 10 }}>
                  Entry Zone
                </div>
                <div className="ia-kpi-value ia-entry-zone">
                  {displayTradePlan.entry_zone}
                </div>
                <div className="ia-kpi-label" style={{ marginTop: 8 }}>
                  Stop Hint
                </div>
                <div className="ia-kpi-value" style={{ fontSize: 15 }}>
                  {displayTradePlan.stop_hint}
                </div>
                <div className="ia-kpi-label" style={{ marginTop: 8 }}>
                  Caution
                </div>
                <div className="ia-kpi-value" style={{ fontSize: 15 }}>
                  {displayTradePlan.caution_note}
                </div>
              </>
            ) : null}
          </div>
        </div>

        {!MARKETING_MODE ? (
          <div className="ia-section-gap">
            <StructuralDiagnostics
              open={showStructural}
              onToggle={() => setShowStructural((prev) => !prev)}
              atmCeOi={`${formatNumber(spotRow?.CE_OI ?? null)} ${directionArrow(spotRow?.CE_OIDir)}`}
              atmPeOi={`${formatNumber(spotRow?.PE_OI ?? null)} ${directionArrow(spotRow?.PE_OIDir)}`}
              atmCeVol={`${formatNumber(spotRow?.CE_Volume ?? null)} ${directionArrow(spotRow?.CE_VolDir)}`}
              atmPeVol={`${formatNumber(spotRow?.PE_Volume ?? null)} ${directionArrow(spotRow?.PE_VolDir)}`}
              institutionalLevels={
                smartMoneyZones.institutional.length
                  ? smartMoneyZones.institutional.map((s) => formatNumber(s)).join(", ")
                  : "-"
              }
              expectedMove={formatNumber(apiTargetProjection?.expectedMove ?? null)}
              shift={intradayEngine.shiftSummary}
              alignmentScore={intelligence?.signals?.alignment_filter?.alignment_score}
              oiVelocityScore={intelligence?.signals?.oi?.oi_velocity_score}
              checklist={[
                { label: "ATM OI Rising", confirmed: !!apiTargetProjection?.confirmation?.bullish?.atm_oi_rising },
                { label: "CE Unwinding", confirmed: !!apiTargetProjection?.confirmation?.bullish?.ce_unwinding },
                { label: "PE Aggressive Build", confirmed: !!apiTargetProjection?.confirmation?.bullish?.pe_aggressive_build },
                { label: "PCR < 0.85", confirmed: !!apiTargetProjection?.confirmation?.bearish?.pcr_below_085 },
              ]}
            />
          </div>
        ) : null}

        <div className="ia-tabs-wrap">
          <div className="ia-tabs">
            {visibleTabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`ia-tab-btn ${
                  activeTab === tab
                    ? "ia-tab-btn-active"
                    : ""
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {activeTab === "overview" ? (
            <div className="ia-tab-pane dashboard-grid">
              <div className="dash-card strike-card">
                <h3>Strike Ladder</h3>
                <div className="ladder">
                  <div className="ladder-header">
                    <span>Call Options (CE OI)</span>
                    <span>Strike</span>
                    <span>Put Options (PE OI)</span>
                  </div>
                  {strikeSlice.map((row) => {
                    const ceOi = Number(row.CE_OI) || 0;
                    const peOi = Number(row.PE_OI) || 0;
                    const ceVol = Number(row.CE_Volume) || 0;
                    const peVol = Number(row.PE_Volume) || 0;
                    const isSpot = String(row.strike) === String(nearestSpotStrike);
                    const isRes = String(row.strike) === String(displayResistance);
                    const isSup = String(row.strike) === String(displaySupport);
                    const interpret =
                      row.PE_Interpretation && row.PE_Interpretation !== "Mixed"
                        ? row.PE_Interpretation
                        : row.CE_Interpretation ?? "Mixed";
                    return (
                      <div
                        key={row.strike}
                        className={[
                          "ladder-row",
                          isSpot ? "spot-row" : "",
                          isRes ? "resistance-row" : "",
                          isSup ? "support-row" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        <div className="ladder-side">
                          <div className="bar-wrap red">
                            <div
                              className="bar"
                              style={{
                                width: `${(ceOi / maxMetrics.ceOi) * 100}%`,
                                minWidth: ceOi > 0 ? "2px" : "0px",
                              }}
                            />
                          </div>
                          <div className="bar-meta">
                            <span>{formatNumber(ceOi)}</span>
                            <span className={row.CE_DeltaOI >= 0 ? "up" : "down"}>
                              {row.CE_DeltaOI >= 0 ? "▲" : "▼"} {formatNumber(Math.abs(row.CE_DeltaOI))}
                            </span>
                          </div>
                          <div className="bar-sub">
                            {formatNumber(ceVol)}{" "}
                            <span className={normalizeDirection(row.CE_VolDir) === "up" ? "up" : normalizeDirection(row.CE_VolDir) === "down" ? "down" : ""}>
                              {directionArrow(row.CE_VolDir)}
                            </span>
                          </div>
                        </div>
                        <div className="ladder-center">
                          <div className="strike">{formatNumber(row.strike)}</div>
                          <div className="interp">{interpret}</div>
                        </div>
                        <div className="ladder-side right">
                          <div className="bar-wrap green">
                            <div
                              className="bar"
                              style={{
                                width: `${(peOi / maxMetrics.peOi) * 100}%`,
                                minWidth: peOi > 0 ? "2px" : "0px",
                              }}
                            />
                          </div>
                          <div className="bar-meta">
                            <span>{formatNumber(peOi)}</span>
                            <span className={row.PE_DeltaOI >= 0 ? "up" : "down"}>
                              {row.PE_DeltaOI >= 0 ? "▲" : "▼"} {formatNumber(Math.abs(row.PE_DeltaOI))}
                            </span>
                          </div>
                          <div className="bar-sub">
                            {formatNumber(peVol)}{" "}
                            <span className={normalizeDirection(row.PE_VolDir) === "up" ? "up" : normalizeDirection(row.PE_VolDir) === "down" ? "down" : ""}>
                              {directionArrow(row.PE_VolDir)}
                            </span>
                          </div>
                        </div>
                        {isRes ? <span className="tag resistance">RESISTANCE</span> : null}
                        {isSup ? <span className="tag support">SUPPORT</span> : null}
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="dash-card double-chart">
                <h3>Call OI & Volume</h3>
                <ReactECharts option={callMiniOption} style={{ height: 240 }} />
                <h3>Put OI & Volume</h3>
                <ReactECharts option={putMiniOption} style={{ height: 240 }} />
              </div>
            </div>
          ) : null}

          {activeTab === "charts" ? (
            <div className="ia-tab-pane chart-grid">
              <div className="chart-card">
                <h3>Open Interest by Strike</h3>
                <ReactECharts option={oiOption} style={{ height: 320 }} />
              </div>
            </div>
          ) : null}

          {activeTab === "heatmap" ? (
            <div className="ia-tab-pane chart-card">
              <h3>OI + Volume Change Heatmap</h3>
              {heatmapOption ? (
                <ReactECharts option={heatmapOption} style={{ height: 320 }} />
              ) : (
                <p className="heatmap-empty">Collecting intraday snapshots.</p>
              )}
            </div>
          ) : null}

          {activeTab === "writers" ? (
            <div className="ia-tab-pane impact-card">
              <h3>Top Writers Activity</h3>
              <div className="writers-grid">
                <div>
                  <strong>CE Writers</strong>
                  {topWriters.ce.length ? topWriters.ce.map((item) => (
                    <div key={`ce-tab-${item.strike}`} className="writer-item ce">
                      <span>{formatNumber(item.strike)}</span>
                      <span>OI+ {formatNumber(item.doi)}</span>
                    </div>
                  )) : <div className="writer-empty">No large CE writing bursts</div>}
                </div>
                <div>
                  <strong>PE Writers</strong>
                  {topWriters.pe.length ? topWriters.pe.map((item) => (
                    <div key={`pe-tab-${item.strike}`} className="writer-item pe">
                      <span>{formatNumber(item.strike)}</span>
                      <span>OI+ {formatNumber(item.doi)}</span>
                    </div>
                  )) : <div className="writer-empty">No large PE writing bursts</div>}
                </div>
              </div>
            </div>
          ) : null}

          {activeTab === "basis" ? (
            <div className="ia-tab-pane impact-card">
              <h3>Futures Basis</h3>
              <div className="basis-grid">
                <div><strong>Synthetic Future</strong><span>{formatNumber(futuresBasis.syntheticFuture)}</span></div>
                <div><strong>Basis</strong><span>{futuresBasis.basis !== null ? `${formatNumber(futuresBasis.basis)} (${futuresBasis.basisPct?.toFixed(2)}%)` : "-"}</span></div>
                <div><strong>Status</strong><span className={`basis-status ${futuresBasis.basisType.toLowerCase()}`}>{futuresBasis.basisType}</span></div>
                <div><strong>Direction</strong><span>{futuresBasis.direction}</span></div>
              </div>
            </div>
          ) : null}

          {activeTab === "option-chain" ? (
            <div className="ia-tab-pane table-wrap">
              <table className="option-chain-table">
                <thead>
                  <tr>
                    <th>CE OI</th>
                    <th>CE DeltaOI</th>
                    <th>CE Volume</th>
                    <th>CE Velocity</th>
                    <th>CE Price</th>
                    <th>CE Interpret</th>
                    <th>Strike</th>
                    <th>PE Volume</th>
                    <th>PE DeltaOI</th>
                    <th>PE OI</th>
                    <th>PE Velocity</th>
                    <th>PE Price</th>
                    <th>PE Interpret</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((row) => {
                    const ceOi = Number(row.CE_OI) || 0;
                    const peOi = Number(row.PE_OI) || 0;
                    const vol = (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0);
                    const isResistance = highlight.ceOiThreshold !== null && ceOi >= highlight.ceOiThreshold;
                    const isSupport = highlight.peOiThreshold !== null && peOi >= highlight.peOiThreshold;
                    const isBattle = highlight.volThreshold !== null && vol >= highlight.volThreshold;
                    const vel = velocityByStrike.get(String(row.strike));
                    return (
                    <tr
                      key={row.strike}
                      className={[
                        String(row.strike) === String(nearestSpotStrike) ? "spot-row" : "",
                        isResistance ? "resistance-row" : "",
                        isSupport ? "support-row" : "",
                        isBattle ? "battle-row" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      <td>{formatNumber(row.CE_OI)}</td>
                      <td>{formatNumber(row.CE_DeltaOI)}</td>
                      <td>{formatNumber(row.CE_Volume)}</td>
                      <td>OI {formatSigned(vel?.ceDoiPerMin)} / Vol {formatSigned(vel?.ceVolPerMin)}</td>
                      <td>
                        {formatNumber(row.CE_LastPrice ?? null)}{" "}
                        <span className={`dir ${normalizeDirection(row.CE_PriceDir) === "up" ? "up" : normalizeDirection(row.CE_PriceDir) === "down" ? "down" : ""}`}>
                          {directionArrow(row.CE_PriceDir)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${row.CE_Interpretation ? row.CE_Interpretation.replace(/\s+/g, "-").toLowerCase() : ""}`}>
                          {row.CE_Interpretation ?? "-"}
                        </span>
                      </td>
                      <td>{formatNumber(row.strike)}</td>
                      <td>{formatNumber(row.PE_Volume)}</td>
                      <td>{formatNumber(row.PE_DeltaOI)}</td>
                      <td>{formatNumber(row.PE_OI)}</td>
                      <td>OI {formatSigned(vel?.peDoiPerMin)} / Vol {formatSigned(vel?.peVolPerMin)}</td>
                      <td>
                        {formatNumber(row.PE_LastPrice ?? null)}{" "}
                        <span className={`dir ${normalizeDirection(row.PE_PriceDir) === "up" ? "up" : normalizeDirection(row.PE_PriceDir) === "down" ? "down" : ""}`}>
                          {directionArrow(row.PE_PriceDir)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${row.PE_Interpretation ? row.PE_Interpretation.replace(/\s+/g, "-").toLowerCase() : ""}`}>
                          {row.PE_Interpretation ?? "-"}
                        </span>
                      </td>
                      <td>{row.signal}</td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {activeTab === "engine-health" ? (
            <div className="ia-tab-pane">
              <EngineHealthPanel data={engineHealth} />
            </div>
          ) : null}
        </div>

        <div className="alert-bar">
          {visibleAlerts.map((item) => (
            <span
              key={`${item.type}-${item.message}`}
              className={`alert-item alert-item-${item.severity} ${
                item.type === "counter" ? "alert-item-counter" : ""
              }`}
            >
              {item.message}
              {item.type === "counter" ? " (Counter-trend)" : ""}
            </span>
          ))}
          {hiddenAlertCount > 0 ? (
            <button
              type="button"
              className="alert-more-btn"
              onClick={() => setShowMoreAlerts((prev) => !prev)}
            >
              {showMoreAlerts ? "Hide More Alerts" : `+${hiddenAlertCount} more alerts`}
            </button>
          ) : null}
        </div>

        {hiddenAlerts.length > 0 ? (
          <div className="alert-bar alert-bar-more">
            {hiddenAlerts.map((item) => (
              <span
                key={`more-${item.type}-${item.message}`}
                className={`alert-item alert-item-${item.severity} ${
                  item.type === "counter" ? "alert-item-counter" : ""
                }`}
              >
                {item.message}
                {item.type === "counter" ? " (Counter-trend)" : ""}
              </span>
            ))}
          </div>
        ) : null}

        {MARKETING_MODE ? (
          <section className="why-optionlens">
            <h3>Why OptionLens?</h3>
            <ul>
              <li>Tracks OI change, not just total OI</li>
              <li>Detects trap probability</li>
              <li>Adaptive regime detection</li>
              <li>Conflict-aware signal arbitration</li>
            </ul>
          </section>
        ) : null}

        <div className="disclaimer">
          This dashboard is for educational and analytical purposes only. We are not SEBI registered.
          No buy/sell recommendation. Market data may be delayed. Contact: <a href="mailto:contact@optionlense.com">contact@optionlense.com</a>
        </div>
      </section>
      <button
        type="button"
        className={`ia-refresh-toggle ${autoRefresh ? "ia-refresh-toggle-on" : "ia-refresh-toggle-off"}`}
        onClick={() => setAutoRefresh((prev) => !prev)}
        title="Toggle auto refresh"
      >
        {autoRefresh ? "Auto Refresh: ON" : "Auto Refresh: OFF"}
      </button>
    </div>
  );
}
