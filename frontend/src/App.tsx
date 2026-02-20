import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

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
    direction: string;
    targetPrimary: number | null;
    targetSecondary: number | null;
    targetNote: string | null;
  } | null;
  rows: SummaryRow[];
};

type HistoryPoint = {
  fetchedAtMs: number;
  label: string;
  spot: number | null;
  rows: SummaryRow[];
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/+$/, "");
const REFRESH_MS = 15000;
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
  const [secondaryTab, setSecondaryTab] = useState<"heatmap" | "shift" | "writers" | "basis">("heatmap");
  const [showTable, setShowTable] = useState(false);

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
      setIndexData(list);
    } catch {
      setStatus((current) => `${current} | Index data unavailable`);
      setIndexData([]);
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

  useEffect(() => {
    setExpiry("");
    loadExpiries();
  }, [symbol, instrumentType, useSample]);

  useEffect(() => {
    if (!expiry) return;
    checkNseHealth();
    loadIndexData();
    loadSummary();
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      checkNseHealth();
      loadIndexData();
      loadSummary();
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [expiry, symbol, instrumentType, useSample, autoRefresh]);

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
  const displayCeDoi = useMemo(() => displayRows.map((row) => row.CE_DeltaOI), [displayRows]);
  const displayPeDoi = useMemo(() => displayRows.map((row) => row.PE_DeltaOI), [displayRows]);

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

  const volumeOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: { data: ["CE Volume", "PE Volume"], textStyle: { color: "#f8f5ee" } },
      grid: { left: 48, right: 32, top: 32, bottom: 60 },
      xAxis: {
        type: "category",
        data: displayStrikes,
        axisLabel: { color: "#d2d8d8", rotate: 45 },
      },
      yAxis: { type: "value", axisLabel: { color: "#d2d8d8" } },
      series: [
        { name: "PE Volume", type: "bar", data: displayPeVol, itemStyle: { color: "#58df7c" } },
        {
          name: "CE Volume",
          type: "bar",
          data: displayCeVol,
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
      ],
    }),
    [displayStrikes, displayCeVol, displayPeVol, nearestSpotStrike, meta?.symbol, meta?.spot]
  );

  const totals = useMemo(() => {
    const sum = (vals: number[]) => vals.reduce((acc, v) => acc + (Number(v) || 0), 0);
    return {
      ceOi: sum(displayCeOi),
      peOi: sum(displayPeOi),
      ceVol: sum(displayCeVol),
      peVol: sum(displayPeVol),
      ceDoi: sum(displayCeDoi),
      peDoi: sum(displayPeDoi),
    };
  }, [displayCeOi, displayPeOi, displayCeVol, displayPeVol, displayCeDoi, displayPeDoi]);

  const pcr = totals.ceOi > 0 ? totals.peOi / totals.ceOi : null;

  const indexNameMap: Record<string, string> = {
    NIFTY: "NIFTY 50",
    BANKNIFTY: "NIFTY BANK",
    FINNIFTY: "NIFTY FIN SERVICE",
  };
  const indexRow = indexData.find((row) => row.indexName === indexNameMap[symbol]);
  const spotValue = meta?.spot ?? indexRow?.last ?? null;
  const spotChange =
    indexRow && typeof indexRow.previousClose === "number"
      ? indexRow.last - indexRow.previousClose
      : null;
  const bias =
    totals.ceOi > totals.peOi
      ? totals.ceDoi >= totals.peDoi
        ? "Bearish (CE buildup)"
        : "Bearish (CE dominance)"
      : totals.peOi > totals.ceOi
        ? totals.peDoi >= totals.ceDoi
          ? "Bullish (PE buildup)"
          : "Bullish (PE dominance)"
        : "Neutral";

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

  const maxPainStrike = useMemo(() => {
    if (!displayRows.length) return null;
    const strikesNumeric = displayRows
      .map((row) => Number(row.strike))
      .filter((value) => !Number.isNaN(value))
      .sort((a, b) => a - b);
    if (!strikesNumeric.length) return null;
    let minPain = Number.POSITIVE_INFINITY;
    let maxPain = strikesNumeric[0];
    strikesNumeric.forEach((strike) => {
      let pain = 0;
      displayRows.forEach((row) => {
        const k = Number(row.strike);
        if (Number.isNaN(k)) return;
        const cePain = Math.max(0, strike - k) * (row.CE_OI || 0);
        const pePain = Math.max(0, k - strike) * (row.PE_OI || 0);
        pain += cePain + pePain;
      });
      if (pain < minPain) {
        minPain = pain;
        maxPain = strike;
      }
    });
    return maxPain;
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

  const targetLevel = useMemo(() => {
    if (bias.startsWith("Bullish")) return resistanceStrike;
    if (bias.startsWith("Bearish")) return supportStrike;
    return null;
  }, [bias, resistanceStrike, supportStrike]);

  const marketState =
    pcr === null ? "UNKNOWN" : pcr > 1.15 ? "BULLISH" : pcr < 0.85 ? "BEARISH" : "RANGE";

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

  const interpretationSummary = useMemo(() => {
    const count = (key: "CE_Interpretation" | "PE_Interpretation") => {
      const map = new Map<string, number>();
      displayRows.forEach((row) => {
        const value = row[key] ?? "Mixed";
        map.set(value, (map.get(value) ?? 0) + 1);
      });
      let top = "Mixed";
      let topCount = 0;
      map.forEach((val, k) => {
        if (val > topCount) {
          top = k;
          topCount = val;
        }
      });
      return top;
    };
    return { ce: count("CE_Interpretation"), pe: count("PE_Interpretation") };
  }, [displayRows]);

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
    const merged = [...intradayEngine.engineAlerts, ...alertItems];
    const unique = Array.from(new Set(merged));
    return unique.slice(0, 8);
  }, [intradayEngine.engineAlerts, alertItems]);

  const maxMetrics = useMemo(() => {
    const max = (values: number[]) => (values.length ? Math.max(...values) : 1);
    return {
      ceOi: max(displayRows.map((row) => Number(row.CE_OI) || 0)),
      peOi: max(displayRows.map((row) => Number(row.PE_OI) || 0)),
      ceVol: max(displayRows.map((row) => Number(row.CE_Volume) || 0)),
      peVol: max(displayRows.map((row) => Number(row.PE_Volume) || 0)),
    };
  }, [displayRows]);

  const marketSummary = useMemo(() => {
    const sorted = [...displayRows]
      .map((row) => Number(row.strike))
      .filter((value) => !Number.isNaN(value))
      .sort((a, b) => a - b);
    if (!sorted.length) {
      return {
        marketBias: "Neutral",
        confidence: "Low",
        reasons: ["Insufficient data"],
        tag: null as string | null,
        keyLevels: { support: supportStrike, resistance: resistanceStrike },
      };
    }

    const atmIndex = sorted.findIndex((strike) => String(strike) === String(nearestSpotStrike));
    const center = atmIndex >= 0 ? atmIndex : Math.floor(sorted.length / 2);
    const start = Math.max(0, center - 3);
    const end = Math.min(sorted.length, start + 7);
    const atmWindow = new Set(sorted.slice(start, end).map(String));
    const atmRows = displayRows.filter((row) => atmWindow.has(String(row.strike)));

    let total_ce_oi_change = 0;
    let total_pe_oi_change = 0;
    let ce_short_buildup_count = 0;
    let pe_short_buildup_count = 0;
    let ce_long_buildup_count = 0;
    let pe_long_buildup_count = 0;
    let ce_short_covering_count = 0;
    let pe_short_covering_count = 0;
    let high_volume_strikes = 0;

    atmRows.forEach((row) => {
      total_ce_oi_change += Number(row.CE_DeltaOI) || 0;
      total_pe_oi_change += Number(row.PE_DeltaOI) || 0;

      if ((row.CE_Interpretation || "").includes("Short Build-up")) ce_short_buildup_count += 1;
      if ((row.PE_Interpretation || "").includes("Short Build-up")) pe_short_buildup_count += 1;
      if ((row.CE_Interpretation || "").includes("Long Build-up")) ce_long_buildup_count += 1;
      if ((row.PE_Interpretation || "").includes("Long Build-up")) pe_long_buildup_count += 1;
      if ((row.CE_Interpretation || "").includes("Short Covering")) ce_short_covering_count += 1;
      if ((row.PE_Interpretation || "").includes("Short Covering")) pe_short_covering_count += 1;

      if (row.CE_VolDir === "↑" || row.PE_VolDir === "↑") high_volume_strikes += 1;
    });

    const call_writing_score =
      ce_short_buildup_count + (total_ce_oi_change > total_pe_oi_change ? 1 : 0);
    const put_writing_score =
      pe_short_buildup_count + (total_pe_oi_change > total_ce_oi_change ? 1 : 0);

    const bullish_pressure = pe_short_covering_count + ce_long_buildup_count;
    const bearish_pressure = ce_short_covering_count + pe_long_buildup_count;

    const spot_change_pct = indexRow?.percChange ?? 0;
    const approxEqual = (a: number, b: number) => Math.abs(a - b) <= 1;

    let marketBias = "Neutral";
    const reasons: string[] = [];

    if (call_writing_score >= 3 && put_writing_score <= 1 && bullish_pressure === 0) {
      marketBias = "Strongly Bearish";
      reasons.push("Heavy call writing near ATM");
      reasons.push("Limited put support below spot");
      reasons.push("No signs of short covering");
    } else if (call_writing_score > put_writing_score && bearish_pressure > bullish_pressure) {
      marketBias = "Bearish";
      reasons.push("Call writers dominating near spot");
      reasons.push("Put support weakening");
      reasons.push("Selling pressure visible");
    } else if (
      approxEqual(call_writing_score, put_writing_score) &&
      approxEqual(bullish_pressure, bearish_pressure) &&
      Math.abs(spot_change_pct) <= 0.4
    ) {
      marketBias = "Range-Bound";
      reasons.push("Both call and put writing visible");
      reasons.push("No aggressive build-up");
      reasons.push("Price lacks directional conviction");
    } else if (put_writing_score > call_writing_score && bullish_pressure > bearish_pressure) {
      marketBias = "Bullish";
      reasons.push("Strong put writing near support");
      reasons.push("Call short covering visible");
      reasons.push("Buyers gaining control");
    } else if (put_writing_score >= 3 && call_writing_score <= 1 && bearish_pressure === 0) {
      marketBias = "Strongly Bullish";
      reasons.push("Aggressive put writing");
      reasons.push("Calls being covered rapidly");
      reasons.push("Strong downside support formed");
    } else {
      reasons.push("No dominant build-up signals near spot");
    }

    const tag =
      ce_short_covering_count >= 2 && pe_short_covering_count >= 2 && high_volume_strikes >= 3
        ? "Volatility Expansion Possible"
        : null;

    const confidenceScore = Math.min(5, Math.abs(call_writing_score - put_writing_score)) * 20;
    const confidence = confidenceScore >= 80 ? "High" : confidenceScore >= 50 ? "Medium" : "Low";

    return {
      marketBias,
      reasons,
      tag,
      confidence,
      keyLevels: { support: supportStrike, resistance: resistanceStrike },
    };
  }, [displayRows, nearestSpotStrike, indexRow?.percChange, supportStrike, resistanceStrike]);

  const topInterpretation = useMemo(() => {
    let best = null as null | {
      strike: number;
      optionType: "CE" | "PE";
      label: string;
      desc: string;
      score: number;
    };
    displayRows.forEach((row) => {
      const ceScore = row.CE_ConfidenceScore ?? 0;
      if (!best || ceScore > best.score) {
        best = {
          strike: row.strike,
          optionType: "CE",
          label: row.CE_Interpretation ?? "Mixed",
          desc: row.CE_InterpretationDesc ?? "Signals are not aligned.",
          score: ceScore,
        };
      }
      const peScore = row.PE_ConfidenceScore ?? 0;
      if (!best || peScore > best.score) {
        best = {
          strike: row.strike,
          optionType: "PE",
          label: row.PE_Interpretation ?? "Mixed",
          desc: row.PE_InterpretationDesc ?? "Signals are not aligned.",
          score: peScore,
        };
      }
    });
    return best;
  }, [displayRows]);

  const atmInfo = useMemo(() => {
    const atmRow = displayRows.find((row) => String(row.strike) === String(nearestSpotStrike));
    if (!atmRow) return { strike: null, bias: "Neutral" };
    const atmVol = (Number(atmRow.CE_Volume) || 0) + (Number(atmRow.PE_Volume) || 0);
    const avgVol =
      displayRows.length
        ? displayRows.reduce(
            (acc, row) => acc + (Number(row.CE_Volume) || 0) + (Number(row.PE_Volume) || 0),
            0
          ) / displayRows.length
        : 0;
    if (avgVol && atmVol > avgVol * 1.2) {
      return { strike: atmRow.strike, bias: "Directional move loading" };
    }
    if (atmRow.CE_DeltaOI > 0 && atmRow.PE_DeltaOI < 0) {
      return { strike: atmRow.strike, bias: "Bullish bias" };
    }
    if (atmRow.PE_DeltaOI > 0 && atmRow.CE_DeltaOI < 0) {
      return { strike: atmRow.strike, bias: "Bearish bias" };
    }
    return { strike: atmRow.strike, bias: "Neutral" };
  }, [displayRows, nearestSpotStrike]);

  const dynamicLevels = useMemo(() => {
    if (!displayRows.length) {
      return { supportTop: [] as Array<{ strike: number; score: number }>, resistanceTop: [] as Array<{ strike: number; score: number }> };
    }
    const maxCeOi = Math.max(...displayRows.map((row) => Number(row.CE_OI) || 0), 1);
    const maxPeOi = Math.max(...displayRows.map((row) => Number(row.PE_OI) || 0), 1);
    const maxCeDoi = Math.max(...displayRows.map((row) => Math.max(0, Number(row.CE_DeltaOI) || 0)), 1);
    const maxPeDoi = Math.max(...displayRows.map((row) => Math.max(0, Number(row.PE_DeltaOI) || 0)), 1);
    const maxCeVol = Math.max(...displayRows.map((row) => Number(row.CE_Volume) || 0), 1);
    const maxPeVol = Math.max(...displayRows.map((row) => Number(row.PE_Volume) || 0), 1);

    const resistanceTop = [...displayRows]
      .map((row) => {
        const score =
          (0.5 * (Number(row.CE_OI) || 0)) / maxCeOi +
          (0.3 * Math.max(0, Number(row.CE_DeltaOI) || 0)) / maxCeDoi +
          (0.2 * (Number(row.CE_Volume) || 0)) / maxCeVol;
        return { strike: row.strike, score: Math.round(score * 100) };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    const supportTop = [...displayRows]
      .map((row) => {
        const score =
          (0.5 * (Number(row.PE_OI) || 0)) / maxPeOi +
          (0.3 * Math.max(0, Number(row.PE_DeltaOI) || 0)) / maxPeDoi +
          (0.2 * (Number(row.PE_Volume) || 0)) / maxPeVol;
        return { strike: row.strike, score: Math.round(score * 100) };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    return { supportTop, resistanceTop };
  }, [displayRows]);

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

  const projectionState = useMemo(() => {
    if (!apiTargetProjection?.state) {
      return { label: "N/A", tone: "neutral" as const };
    }
    if (apiTargetProjection.state === "BREAKOUT_UP") {
      return { label: "Breakout Up", tone: "bull" as const };
    }
    if (apiTargetProjection.state === "BREAKOUT_DOWN") {
      return { label: "Breakout Down", tone: "bear" as const };
    }
    return { label: "Range", tone: "neutral" as const };
  }, [apiTargetProjection]);

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

  const expiryEngine = useMemo(() => {
    const spot = typeof spotValue === "number" ? spotValue : null;
    if (spot === null || maxPainStrike === null) {
      return {
        pinningZone: false,
        pinningProbability: 0,
        expiryTrapLikely: false,
        premiumCrush: false,
        expiryRangeLock: false,
        manipulationRisk: 0,
      };
    }
    const distancePct = Math.abs(spot - Number(maxPainStrike)) / Math.max(1, spot) * 100;
    const pinningZone = distancePct < 0.3;
    const pinningProbability = Math.max(0, Math.min(100, Math.round((0.3 - distancePct) / 0.3 * 100)));

    const prev = history.length >= 2 ? history[history.length - 2] : null;
    const prevVol = prev
      ? prev.rows.reduce((sum, r) => sum + (Number(r.CE_Volume) || 0) + (Number(r.PE_Volume) || 0), 0)
      : 0;
    const currVol = displayRows.reduce((sum, r) => sum + (Number(r.CE_Volume) || 0) + (Number(r.PE_Volume) || 0), 0);
    const quickVolumeDrop = prevVol > 0 ? currVol < prevVol * 0.85 : false;

    const expiryTrapLikely =
      (autoTargetProjection.breakoutUp || autoTargetProjection.breakoutDown) &&
      intradayEngine.weakParticipation &&
      quickVolumeDrop;

    const expiryRangeLock =
      supportStrike !== null &&
      resistanceStrike !== null &&
      spot >= Number(supportStrike) &&
      spot <= Number(resistanceStrike);

    const premiumCrush = false;
    const manipulationRisk = Math.max(
      0,
      Math.min(
        100,
        (pinningZone ? 30 : 0) +
          (expiryTrapLikely ? 40 : 0) +
          (expiryRangeLock ? 20 : 0) +
          (quickVolumeDrop ? 10 : 0)
      )
    );

    return {
      pinningZone,
      pinningProbability,
      expiryTrapLikely,
      premiumCrush,
      expiryRangeLock,
      manipulationRisk,
    };
  }, [
    spotValue,
    maxPainStrike,
    history,
    displayRows,
    autoTargetProjection.breakoutUp,
    autoTargetProjection.breakoutDown,
    intradayEngine.weakParticipation,
    supportStrike,
    resistanceStrike,
  ]);

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

  const probabilityFill = useMemo(() => {
    if (probabilityBias.label === "Bearish") {
      return { width: breakoutModel.downProbability, tone: "bear" as const };
    }
    if (probabilityBias.label === "Bullish") {
      return { width: breakoutModel.upProbability, tone: "bull" as const };
    }
    return {
      width: Math.max(breakoutModel.upProbability, breakoutModel.downProbability),
      tone: "neutral" as const,
    };
  }, [probabilityBias.label, breakoutModel.upProbability, breakoutModel.downProbability]);

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

  const interpretationNarrative = useMemo(() => {
    const lines: string[] = [];
    const topCeWriter = topWriters.ce[0] ?? null;
    const topPeWriter = topWriters.pe[0] ?? null;

    if (topCeWriter) {
      lines.push(
        `Strong CE writing near ${formatNumber(topCeWriter.strike)} suggests upside capped.`
      );
    } else if (resistanceStrike !== null) {
      lines.push(`Call-side resistance remains near ${formatNumber(resistanceStrike)}.`);
    }

    if (topPeWriter) {
      const peVsCe = topCeWriter ? topPeWriter.doi - topCeWriter.doi : topPeWriter.doi;
      lines.push(
        peVsCe >= 0
          ? `PE support near ${formatNumber(topPeWriter.strike)} is holding with active participation.`
          : `PE support near ${formatNumber(topPeWriter.strike)} is present but weaker than call pressure.`
      );
    } else if (supportStrike !== null) {
      lines.push(`Support is currently seen near ${formatNumber(supportStrike)}.`);
    }

    if (supportStrike !== null && resistanceStrike !== null) {
      if (breakoutModel.downProbability > 60) {
        lines.push(
          `Breakdown below ${formatNumber(supportStrike)} is likely if volume expands.`
        );
      } else if (breakoutModel.upProbability > 60) {
        lines.push(
          `Breakout above ${formatNumber(resistanceStrike)} is likely if call OI unwinds.`
        );
      } else {
        lines.push(
          `Range is likely between ${formatNumber(supportStrike)} and ${formatNumber(resistanceStrike)} unless ATM volume shocks.`
        );
      }
    }

    return {
      title:
        probabilityBias.label === "Bullish"
          ? "Bullish structure"
          : probabilityBias.label === "Bearish"
            ? "Bearish structure"
            : "Range structure",
      lines: lines.slice(0, 3),
      confidence: breakoutModel.confidence,
    };
  }, [
    topWriters.ce,
    topWriters.pe,
    resistanceStrike,
    supportStrike,
    breakoutModel.downProbability,
    breakoutModel.upProbability,
    breakoutModel.confidence,
    probabilityBias.label,
  ]);

  const heatmapOption = useMemo(() => {
    const minuteMap = new Map<string, HistoryPoint>();
    history.forEach((point) => {
      const key = new Date(point.fetchedAtMs).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      });
      const existing = minuteMap.get(key);
      if (!existing || point.fetchedAtMs > existing.fetchedAtMs) {
        minuteMap.set(key, point);
      }
    });
    const recent = [...minuteMap.values()]
      .sort((a, b) => a.fetchedAtMs - b.fetchedAtMs)
      .slice(-120);
    if (!recent.length || !displayRows.length) return null;
    const xLabels = recent.map((point) => point.label);
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
        points.push([xIdx, yIdx, Number((directional * volFactor).toFixed(2))]);
      });
    });
    const maxAbs = Math.max(1, ...points.map((point) => Math.abs(point[2])));

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
        },
      ],
    };
  }, [history, displayRows, nearestSpotStrike]);

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Intraday Dashboard</p>
          <h1>Optionlens</h1>
          <p className="subhead">
            Live CE/PE open interest and volume across strikes. Auto refreshes every 15s.
          </p>
        </div>
        <div className="meta">
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
          <button type="button" onClick={loadSummary}>
            Refresh now
          </button>
        </div>

        <div className="status">
          {status}
          {nseStatus === "blocked" && nseMessage ? ` | NSE: ${LIVE_DATA_UNAVAILABLE_MSG}` : ""}
        </div>

        <div className="summary-bar">
          <span className="summary-title">{indexNameMap[symbol] ?? symbol}</span>
          <span>
            Spot: {formatNumber(spotValue)}{" "}
            {spotChange !== null ? (
              <span className={`spot-change ${spotChange >= 0 ? "up" : "down"}`}>
                {spotChange >= 0 ? "▲" : "▼"} {formatNumber(Math.abs(spotChange))}
              </span>
            ) : null}
          </span>
          <span>
            % Change:{" "}
            <span className={`spot-change ${(indexRow?.percChange ?? 0) >= 0 ? "up" : "down"}`}>
              {indexRow?.percChange !== undefined ? `${indexRow?.percChange.toFixed(2)}%` : "-"}
            </span>
          </span>
          <span>Exp: {meta?.expiry ?? "-"}</span>
          <span>Phase: {intradayEngine.sessionPhase}</span>
          <span>PCR: {pcr ? pcr.toFixed(2) : "-"}</span>
          <span>Max Pain: {formatNumber(maxPainStrike)}</span>
          <span>
            Projection:{" "}
            <span className={`trend-pill ${projectionState.tone}`}>{projectionState.label}</span>
          </span>
          <span>
            Trend:{" "}
            <span className={`trend-pill ${probabilityBias.label === "Bullish" ? "bull" : probabilityBias.label === "Bearish" ? "bear" : "neutral"}`}>
              {probabilityBias.label}
            </span>
          </span>
          <span>Updated: {meta?.timestamp ?? lastUpdated ?? "-"}</span>
        </div>

        <div className="decision-row">
          <div className="decision-card">
            <h3>Market Bias + Probability</h3>
            <div className="decision-main">
              <span
                className={`bias-pill ${
                  probabilityBias.label === "Bullish"
                    ? "bull"
                    : probabilityBias.label === "Bearish"
                      ? "bear"
                      : "neutral"
                }`}
              >
                {probabilityBias.label}
              </span>
              <span className="pill-inline">Conf: {probabilityBias.confidence}</span>
            </div>
            <div className="prob-track">
              <div
                className={`prob-up ${probabilityFill.tone}`}
                style={{ width: `${probabilityFill.width}%` }}
              />
            </div>
            <div className="prob-legend">
              <span>Bull {breakoutModel.upProbability}%</span>
              <span>Bear {breakoutModel.downProbability}%</span>
              <span>Conf {breakoutModel.confidence}%</span>
            </div>
            <p className="decision-sub">{breakoutModel.signal}</p>
          </div>
          <div className="decision-card">
            <h3>Key Levels</h3>
            <div className="decision-kv">
              <div><strong>Resistance</strong><span>{formatNumber(resistanceStrike)}</span></div>
              <div><strong>Support</strong><span>{formatNumber(supportStrike)}</span></div>
              <div><strong>Target 1</strong><span>{formatNumber(effectiveTargetProjection.target1)}</span></div>
              <div><strong>Target 2</strong><span>{formatNumber(effectiveTargetProjection.target2)}</span></div>
              <div><strong>Target State</strong><span>{effectiveTargetProjection.status}</span></div>
              <div><strong>Target Flow</strong><span>{effectiveTargetProjection.direction ?? "-"}</span></div>
              <div><strong>Target Note</strong><span>{effectiveTargetProjection.note ?? "-"}</span></div>
              <div><strong>Phase</strong><span>{intradayEngine.sessionPhase}</span></div>
              <div><strong>Shift</strong><span>{intradayEngine.shiftSummary}</span></div>
              <div><strong>Trap</strong><span>{intradayEngine.trapRisk} ({intradayEngine.trapScore}%)</span></div>
              <div><strong>Institutional</strong><span>{smartMoneyZones.institutional.length ? smartMoneyZones.institutional.map((s) => formatNumber(s)).join(", ") : "-"}</span></div>
              <div><strong>Acceleration</strong><span>{smartMoneyZones.acceleration.length ? smartMoneyZones.acceleration.join(" | ") : "-"}</span></div>
              <div><strong>Scalp Momentum</strong><span>{scalpingEngine.momentumScore}%</span></div>
              <div><strong>VWAP Bias</strong><span>{scalpingEngine.vwapBias}</span></div>
              <div><strong>Quick Target</strong><span>{formatNumber(scalpingEngine.quickTarget)}</span></div>
              <div><strong>Reversal Risk</strong><span>{scalpingEngine.reversalRisk}%</span></div>
              <div><strong>Expiry Risk</strong><span>{expiryEngine.manipulationRisk}%</span></div>
              <div><strong>Pinning</strong><span>{expiryEngine.pinningZone ? `Yes (${expiryEngine.pinningProbability}%)` : "No"}</span></div>
            </div>
          </div>
          <div className="decision-card">
            <h3>Interpretation</h3>
            <div className="decision-main">
              <span className="pill-inline">{interpretationNarrative.title}</span>
              <span className="pill-inline">Conf: {interpretationNarrative.confidence}%</span>
            </div>
            <ul className="engine-list">
              {interpretationNarrative.lines.map((item) => (
                <li key={`interp-${item}`}>{item}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="auto-interpret">
          <div className="market-summary">
            <h4>
              Market Summary{" "}
              <span
                className={`bias-pill ${
                  marketSummary.marketBias.toLowerCase().includes("bullish")
                    ? "bull"
                    : marketSummary.marketBias.toLowerCase().includes("bearish")
                      ? "bear"
                      : "neutral"
                }`}
              >
                {marketSummary.marketBias}
              </span>
              <span className="pill-inline">Confidence: {marketSummary.confidence}</span>
            </h4>
            <ul>
              {marketSummary.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
              {marketSummary.tag ? <li>⚠ {marketSummary.tag}</li> : null}
            </ul>
            <div className="key-levels">
              <span>Resistance: {formatNumber(marketSummary.keyLevels.resistance)}</span>
              <span>Support: {formatNumber(marketSummary.keyLevels.support)}</span>
            </div>
          </div>
          <div className="interpret-card">
            <h4>Interpretation</h4>
            <div className="interpret-label">
              {topInterpretation
                ? `${topInterpretation.label} at ${formatNumber(topInterpretation.strike)} ${topInterpretation.optionType}`
                : "Mixed"}
            </div>
            <ul>
              <li>{topInterpretation?.desc ?? "Signals are not aligned."}</li>
              <li>Confidence: {topInterpretation?.score ?? 0}</li>
            </ul>
          </div>
        </div>

        <div className="impact-grid">
          <div className="impact-card">
            <h3>Intraday Decision Engine</h3>
            <div className="basis-grid">
              <div><strong>Session</strong><span>{intradayEngine.sessionPhase}</span></div>
              <div><strong>Trap Detector</strong><span className={intradayEngine.trapLikely ? "down" : "up"}>{intradayEngine.trapLikely ? "Likely false move" : "No trap setup"}</span></div>
              <div><strong>Shift Tracker</strong><span>{intradayEngine.shiftSummary}</span></div>
            </div>
            <ul className="engine-list">
              {intradayEngine.engineAlerts.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="impact-card">
            <h3>Breakout Probability</h3>
            <div className="prob-track">
              <div className="prob-up" style={{ width: `${breakoutModel.upProbability}%` }} />
            </div>
            <div className="prob-legend">
              <span>Bullish: {breakoutModel.upProbability}%</span>
              <span>Bearish: {breakoutModel.downProbability}%</span>
              <span>Confidence: {breakoutModel.confidence}%</span>
            </div>
            <p className="impact-signal">{breakoutModel.signal}</p>
            <ul>
              {breakoutModel.factors.map((factor) => (
                <li key={factor}>{factor}</li>
              ))}
            </ul>
          </div>

          <div className="impact-card">
            <h3>Dynamic S/R Score</h3>
            <div className="sr-columns">
              <div>
                <strong>Support (PE)</strong>
                {dynamicLevels.supportTop.map((entry) => (
                  <div key={`sup-${entry.strike}`} className="sr-item support">
                    <span>{formatNumber(entry.strike)}</span>
                    <span>{entry.score}</span>
                  </div>
                ))}
              </div>
              <div>
                <strong>Resistance (CE)</strong>
                {dynamicLevels.resistanceTop.map((entry) => (
                  <div key={`res-${entry.strike}`} className="sr-item resistance">
                    <span>{formatNumber(entry.strike)}</span>
                    <span>{entry.score}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="impact-card">
            <h3>Top Writers Activity (Proxy)</h3>
            <div className="writers-grid">
              <div>
                <strong>Call Writers (CE)</strong>
                {topWriters.ce.length ? (
                  topWriters.ce.map((item) => (
                    <div key={`cew-${item.strike}`} className="writer-item ce">
                      <span>{formatNumber(item.strike)}</span>
                      <span>OI+ {formatNumber(item.doi)}</span>
                      <span>Vol {formatNumber(item.volume)}</span>
                    </div>
                  ))
                ) : (
                  <div className="writer-empty">No large CE writing bursts</div>
                )}
              </div>
              <div>
                <strong>Put Writers (PE)</strong>
                {topWriters.pe.length ? (
                  topWriters.pe.map((item) => (
                    <div key={`pew-${item.strike}`} className="writer-item pe">
                      <span>{formatNumber(item.strike)}</span>
                      <span>OI+ {formatNumber(item.doi)}</span>
                      <span>Vol {formatNumber(item.volume)}</span>
                    </div>
                  ))
                ) : (
                  <div className="writer-empty">No large PE writing bursts</div>
                )}
              </div>
            </div>
          </div>

          <div className="impact-card">
            <h3>Futures Basis Confirmation</h3>
            <div className="basis-grid">
              <div><strong>Method</strong><span>{futuresBasis.method}</span></div>
              <div><strong>Synthetic Future</strong><span>{formatNumber(futuresBasis.syntheticFuture)}</span></div>
              <div><strong>Basis</strong><span>{futuresBasis.basis !== null ? `${formatNumber(futuresBasis.basis)} (${futuresBasis.basisPct?.toFixed(2)}%)` : "-"}</span></div>
              <div><strong>Status</strong><span className={`basis-status ${futuresBasis.basisType.toLowerCase()}`}>{futuresBasis.basisType}</span></div>
              <div><strong>Directional Check</strong><span>{futuresBasis.direction}</span></div>
            </div>
          </div>
        </div>

        <div className="chart-card heatmap-card">
          <h3>OI + Volume Change Heatmap (rolling {HEATMAP_WINDOW_MINUTES}m)</h3>
          {heatmapOption ? (
            <ReactECharts option={heatmapOption} style={{ height: 320 }} />
          ) : (
            <p className="heatmap-empty">Collecting intraday snapshots. Heatmap appears after a few refreshes.</p>
          )}
        </div>

        <div className="dashboard-grid">
          <div className="dash-card strike-card">
            <h3>Strike Prices</h3>
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
                const isRes = String(row.strike) === String(resistanceStrike);
                const isSup = String(row.strike) === String(supportStrike);
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
                        <div className="bar" style={{ width: `${(ceOi / maxMetrics.ceOi) * 100}%` }} />
                      </div>
                      <div className="bar-meta">
                        <span>{formatNumber(ceOi)}</span>
                        <span className={row.CE_DeltaOI >= 0 ? "up" : "down"}>
                          {row.CE_DeltaOI >= 0 ? "↑" : "↓"} {formatNumber(Math.abs(row.CE_DeltaOI))}
                        </span>
                      </div>
                      <div className="bar-sub">
                        {formatNumber(ceVol)}{" "}
                        <span className={row.CE_VolDir === "↑" ? "up" : row.CE_VolDir === "↓" ? "down" : ""}>
                          {row.CE_VolDir ?? "→"}
                        </span>
                      </div>
                    </div>
                    <div className="ladder-center">
                      <div className="strike">{formatNumber(row.strike)}</div>
                      <div className="interp">{interpret}</div>
                    </div>
                    <div className="ladder-side right">
                      <div className="bar-wrap green">
                        <div className="bar" style={{ width: `${(peOi / maxMetrics.peOi) * 100}%` }} />
                      </div>
                      <div className="bar-meta">
                        <span>{formatNumber(peOi)}</span>
                        <span className={row.PE_DeltaOI >= 0 ? "up" : "down"}>
                          {row.PE_DeltaOI >= 0 ? "↑" : "↓"} {formatNumber(Math.abs(row.PE_DeltaOI))}
                        </span>
                      </div>
                      <div className="bar-sub">
                        {formatNumber(peVol)}{" "}
                        <span className={row.PE_VolDir === "↑" ? "up" : row.PE_VolDir === "↓" ? "down" : ""}>
                          {row.PE_VolDir ?? "→"}
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
            <div className="mini-summary">
              <div><strong>Support</strong><span>{formatNumber(supportStrike)}</span></div>
              <div><strong>Resistance</strong><span>{formatNumber(resistanceStrike)}</span></div>
              <div><strong>Target</strong><span>{targetLevel ? formatNumber(targetLevel) : "Range"}</span></div>
              <div><strong>Alerts</strong><span>{alertItems[0] ?? "-"}</span></div>
              <div><strong>ATM</strong><span>{formatNumber(atmInfo.strike)}</span></div>
            </div>
          </div>
          <div className="dash-card signal-card">
            <h3>Market Signals</h3>
            <div className="signal-row support">
              <span className="dot support" /> Support:
              <span className="pill-inline">{formatNumber(supportStrike)} PE</span>
            </div>
            <div className="signal-row resistance">
              <span className="dot resistance" /> Resistance:
              <span className="pill-inline">{formatNumber(resistanceStrike)} CE</span>
            </div>
            <div className="signal-row battle">
              <span className="dot battle" /> Max Volume:
              <span className="pill-inline">{formatNumber(maxVolumeStrike)}</span>
            </div>
            <div className="signal-row">
              Trend: <span className="pill-inline">{marketState}</span>
            </div>
            <div className="signal-row">
              CE: <span className="pill-inline">{interpretationSummary.ce}</span>
            </div>
            <div className="signal-row">
              PE: <span className="pill-inline">{interpretationSummary.pe}</span>
            </div>
            <div className="signal-section">Actions</div>
            <div className="signal-row">Watch for OI Unwinding</div>
            <div className="signal-row">
              Range:
              <span className="pill-inline">
                {formatNumber(supportStrike)} - {formatNumber(resistanceStrike)}
              </span>
            </div>
          </div>
        </div>

        <div className="legend">
          <span className="legend-item resistance">Highest CE OI =&gt; Resistance</span>
          <span className="legend-item support">Highest PE OI =&gt; Support</span>
          <span className="legend-item battle">Highest Volume =&gt; Battle zone</span>
        </div>

        <div className="secondary-tabs">
          <div className="tab-head">
            <button type="button" className={secondaryTab === "heatmap" ? "tab-btn active" : "tab-btn"} onClick={() => setSecondaryTab("heatmap")}>Heatmap</button>
            <button type="button" className={secondaryTab === "shift" ? "tab-btn active" : "tab-btn"} onClick={() => setSecondaryTab("shift")}>Shift</button>
            <button type="button" className={secondaryTab === "writers" ? "tab-btn active" : "tab-btn"} onClick={() => setSecondaryTab("writers")}>Writers</button>
            <button type="button" className={secondaryTab === "basis" ? "tab-btn active" : "tab-btn"} onClick={() => setSecondaryTab("basis")}>Basis</button>
          </div>
          {secondaryTab === "heatmap" ? (
            <div className="chart-card">
              <h3>OI + Volume Change Heatmap</h3>
              {heatmapOption ? <ReactECharts option={heatmapOption} style={{ height: 320 }} /> : <p className="heatmap-empty">Collecting intraday snapshots.</p>}
            </div>
          ) : null}
          {secondaryTab === "shift" ? (
            <div className="impact-card">
              <h3>Shift Tracker</h3>
              <div className="basis-grid">
                <div><strong>Session</strong><span>{intradayEngine.sessionPhase}</span></div>
                <div><strong>Shift</strong><span>{intradayEngine.shiftSummary}</span></div>
                <div><strong>Trap</strong><span>{intradayEngine.trapMessage}</span></div>
                <div><strong>Trap Risk</strong><span>{intradayEngine.trapRisk} ({intradayEngine.trapScore}%)</span></div>
                <div><strong>Institutional Zone</strong><span>{smartMoneyZones.institutional.length ? smartMoneyZones.institutional.map((s) => formatNumber(s)).join(", ") : "-"}</span></div>
                <div><strong>Acceleration Zone</strong><span>{smartMoneyZones.acceleration.length ? smartMoneyZones.acceleration.join(" | ") : "-"}</span></div>
                <div><strong>Scalp Fast Move</strong><span>{scalpingEngine.fastMove ? "Yes" : "No"}</span></div>
                <div><strong>Scalp Exit</strong><span>{scalpingEngine.exitSignal ? "Exit likely" : "Hold"}</span></div>
                <div><strong>Expiry Trap</strong><span>{expiryEngine.expiryTrapLikely ? "Likely" : "No"}</span></div>
                <div><strong>Range Lock</strong><span>{expiryEngine.expiryRangeLock ? "Yes" : "No"}</span></div>
              </div>
            </div>
          ) : null}
          {secondaryTab === "writers" ? (
            <div className="impact-card">
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
          {secondaryTab === "basis" ? (
            <div className="impact-card">
              <h3>Futures Basis</h3>
              <div className="basis-grid">
                <div><strong>Synthetic Future</strong><span>{formatNumber(futuresBasis.syntheticFuture)}</span></div>
                <div><strong>Basis</strong><span>{futuresBasis.basis !== null ? `${formatNumber(futuresBasis.basis)} (${futuresBasis.basisPct?.toFixed(2)}%)` : "-"}</span></div>
                <div><strong>Status</strong><span className={`basis-status ${futuresBasis.basisType.toLowerCase()}`}>{futuresBasis.basisType}</span></div>
                <div><strong>Direction</strong><span>{futuresBasis.direction}</span></div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="alert-bar">
          {combinedAlerts.map((item) => (
            <span key={item} className="alert-item">
              {item}
            </span>
          ))}
        </div>

        <div className="chart-intro">
          <h3>Interpretation</h3>
          <p>
            Bars show OI, lines show volume. Spot line highlights ATM. Use Support/Resistance and
            Bias for quick context.
          </p>
        </div>

        <div className="chart-grid">
          <div className="chart-card">
            <h3>Open Interest by Strike</h3>
            <ReactECharts option={oiOption} style={{ height: 320 }} />
          </div>
          <div className="chart-card">
            <h3>Volume by Strike</h3>
            <ReactECharts option={volumeOption} style={{ height: 320 }} />
          </div>
        </div>

        <div className="table-toolbar">
          <button type="button" onClick={() => setShowTable((prev) => !prev)}>
            {showTable ? "Hide Option Chain" : "Show Option Chain"}
          </button>
        </div>

        {showTable ? <div className="table-wrap">
          <table>
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
                const isResistance =
                  highlight.ceOiThreshold !== null && ceOi >= highlight.ceOiThreshold;
                const isSupport =
                  highlight.peOiThreshold !== null && peOi >= highlight.peOiThreshold;
                const isBattle =
                  highlight.volThreshold !== null && vol >= highlight.volThreshold;
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
                    <span className={`dir ${row.CE_PriceDir === "↑" ? "up" : row.CE_PriceDir === "↓" ? "down" : ""}`}>
                      {row.CE_PriceDir ?? "→"}
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
                    <span className={`dir ${row.PE_PriceDir === "↑" ? "up" : row.PE_PriceDir === "↓" ? "down" : ""}`}>
                      {row.PE_PriceDir ?? "→"}
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
        </div> : null}

        <div className="disclaimer">
          This dashboard is for educational and analytical purposes only. We are not SEBI registered.
          No buy/sell recommendation.
        </div>
      </section>
    </div>
  );
}
