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
  PE_OI: number;
  PE_DeltaOI: number;
  PE_Volume: number;
  PE_LastPrice?: number;
  PE_PriceChange?: number;
  PE_PriceDir?: string;
  PE_OIDir?: string;
  PE_VolDir?: string;
  PE_Interpretation?: string;
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
  rows: SummaryRow[];
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const REFRESH_MS = 15000;

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

export default function App() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [instrumentType, setInstrumentType] = useState("Indices");
  const [expiries, setExpiries] = useState<string[]>([]);
  const [expiry, setExpiry] = useState<string>("");
  const [strikes, setStrikes] = useState<(number | string)[]>([]);
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
      const strikeList = Array.isArray(data.strikes) ? data.strikes : [];
      setExpiries(list);
      setStrikes(strikeList);
      setExpiry((current) => (current && list.includes(current) ? current : list[0] ?? ""));
      setStatus(list.length ? `Loaded ${list.length} expiries.` : "No expiries returned.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setStatus(`Failed to load expiries: ${msg}`);
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
      setLastUpdated(new Date().toLocaleTimeString("en-IN"));
      setStatus(`Loaded ${data.rows?.length ?? 0} strikes.`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setStatus(`Failed to load summary: ${msg}`);
      setRows([]);
      setMeta(null);
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
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setStatus((current) => `${current} | Index data error: ${msg}`);
      setIndexData([]);
    }
  }

  async function checkNseHealth() {
    setNseStatus("checking");
    setNseMessage("");
    try {
      const res = await fetch(`${API_BASE}/health/nse`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const message = data?.detail || "NSE blocked";
        throw new Error(message);
      }
      setNseStatus("ok");
    } catch (error) {
      setNseStatus("blocked");
      const message = error instanceof Error ? error.message : "NSE blocked";
      setNseMessage(message);
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
  const marketState =
    pcr === null ? "UNKNOWN" : pcr > 1.15 ? "BULLISH" : pcr < 0.85 ? "BEARISH" : "RANGE";
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
    const start = Math.max(0, center - 5);
    const end = Math.min(strikesSorted.length, start + 11);
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

  const maxCeDoiStrike = useMemo(() => {
    let best = null as SummaryRow | null;
    displayRows.forEach((row) => {
      if (!best || row.CE_DeltaOI > best.CE_DeltaOI) best = row;
    });
    return best?.strike ?? null;
  }, [displayRows]);

  const maxPeDoiStrike = useMemo(() => {
    let best = null as SummaryRow | null;
    displayRows.forEach((row) => {
      if (!best || row.PE_DeltaOI > best.PE_DeltaOI) best = row;
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
      xAxis: {
        type: "category",
        data: displayStrikes,
        axisLabel: { color: "#c7cbd4", rotate: 0 },
      },
      yAxis: [
        { type: "value", axisLabel: { color: "#c7cbd4" } },
        { type: "value", axisLabel: { color: "#c7cbd4" } },
      ],
      series: [
        { name: "Call OI", type: "bar", data: displayCeOi, itemStyle: { color: "#2f6bd2" } },
        {
          name: "Call Volume",
          type: "line",
          yAxisIndex: 1,
          data: displayCeVol,
          smooth: true,
          lineStyle: { color: "#e6e6e6", width: 2 },
          itemStyle: { color: "#e6e6e6" },
        },
      ],
    }),
    [displayStrikes, displayCeOi, displayCeVol]
  );

  const putMiniOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { left: 36, right: 28, top: 28, bottom: 36 },
      xAxis: {
        type: "category",
        data: displayStrikes,
        axisLabel: { color: "#c7cbd4", rotate: 0 },
      },
      yAxis: [
        { type: "value", axisLabel: { color: "#c7cbd4" } },
        { type: "value", axisLabel: { color: "#c7cbd4" } },
      ],
      series: [
        { name: "Put OI", type: "bar", data: displayPeOi, itemStyle: { color: "#4a9a67" } },
        {
          name: "Put Volume",
          type: "line",
          yAxisIndex: 1,
          data: displayPeVol,
          smooth: true,
          lineStyle: { color: "#b7f5cf", width: 2 },
          itemStyle: { color: "#b7f5cf" },
        },
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
    return {
      ce: count("CE_Interpretation"),
      pe: count("PE_Interpretation"),
    };
  }, [displayRows]);

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Intraday Dashboard</p>
          <h1>NSE OI + Volume Live</h1>
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
          {nseStatus === "blocked" && nseMessage ? ` | NSE: ${nseMessage}` : ""}
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
          <span>Exp: {meta?.expiry ?? "-"}</span>
          <span>
            Market: <strong className={`market-${marketState.toLowerCase()}`}>{marketState}</strong>
          </span>
          <span>PCR: {pcr ? pcr.toFixed(2) : "-"}</span>
          <span>Updated: {meta?.timestamp ?? lastUpdated ?? "-"}</span>
        </div>

        <div className="dashboard-grid">
          <div className="dash-card strike-card">
            <h3>Strike Prices</h3>
            <table>
              <thead>
                <tr>
                  <th>Strike</th>
                  <th>CE OI</th>
                  <th>ΔOI</th>
                  <th>PE ΔOI</th>
                </tr>
              </thead>
              <tbody>
                {strikeSlice.map((row) => (
                  <tr
                    key={row.strike}
                    className={[
                      String(row.strike) === String(nearestSpotStrike) ? "spot-row" : "",
                      String(row.strike) === String(resistanceStrike) ? "resistance-row" : "",
                      String(row.strike) === String(supportStrike) ? "support-row" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <td>{formatNumber(row.strike)}</td>
                    <td>{formatNumber(row.CE_OI)}</td>
                    <td className={row.CE_DeltaOI >= 0 ? "up" : "down"}>
                      {row.CE_DeltaOI >= 0 ? "+" : ""}
                      {formatNumber(row.CE_DeltaOI)}
                    </td>
                    <td className={row.PE_DeltaOI >= 0 ? "up" : "down"}>
                      {row.PE_DeltaOI >= 0 ? "+" : ""}
                      {formatNumber(row.PE_DeltaOI)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="dash-card">
            <h3>Call OI & Volume</h3>
            <ReactECharts option={callMiniOption} style={{ height: 260 }} />
          </div>
          <div className="dash-card">
            <h3>Put OI & Volume</h3>
            <ReactECharts option={putMiniOption} style={{ height: 260 }} />
          </div>
          <div className="dash-card signal-card">
            <h3>Market Signals</h3>
            <div className="signal-row support">
              <span className="dot support" /> Support: {formatNumber(supportStrike)} PE
            </div>
            <div className="signal-row resistance">
              <span className="dot resistance" /> Resistance: {formatNumber(resistanceStrike)} CE
            </div>
            <div className="signal-row battle">
              <span className="dot battle" /> Max Volume: {formatNumber(maxVolumeStrike)}
            </div>
            <div className="signal-row">Trend: {marketState}</div>
            <div className="signal-row">Bias: {bias}</div>
            <div className="signal-row">CE: {interpretationSummary.ce}</div>
            <div className="signal-row">PE: {interpretationSummary.pe}</div>
            <div className="signal-section">Actions</div>
            <div className="signal-row">Watch for OI Unwinding</div>
            <div className="signal-row">
              Range: {formatNumber(supportStrike)} - {formatNumber(resistanceStrike)}
            </div>
          </div>
        </div>

        <div className="legend">
          <span className="legend-item resistance">Highest CE OI =&gt; Resistance</span>
          <span className="legend-item support">Highest PE OI =&gt; Support</span>
          <span className="legend-item battle">Highest Volume =&gt; Battle zone</span>
        </div>

        <div className="alert-bar">
          {alertItems.map((item) => (
            <span key={item} className="alert-item">
              {item}
            </span>
          ))}
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

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>CE OI</th>
                <th>CE DeltaOI</th>
                <th>CE Volume</th>
                <th>CE Price</th>
                <th>CE Interpret</th>
                <th>Strike</th>
                <th>PE Volume</th>
                <th>PE DeltaOI</th>
                <th>PE OI</th>
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
        </div>
      </section>
    </div>
  );
}
