import { useCallback, useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import "../styles/analytics.css";

const BASE = "http://127.0.0.1:8000/api/v2/local";

// ── Types ────────────────────────────────────────────────────────────────────

interface SummaryData {
  from: string;
  to: string;
  symbol: string;
  total_signals: number;
  wins: number;
  losses: number;
  big_wins: number;
  expired: number;
  win_rate: number;
  avg_rr_realized: number | null;
  avg_rr_predicted: number | null;
  signals_per_day: number;
  net_edge: number;
  by_signal_type: Array<{
    signal_type: string;
    n: number;
    wins: number;
    win_rate: number;
    avg_rr: number | null;
  }>;
}

interface TimelineSeries {
  date: string;
  n: number;
  wins: number;
  win_rate: number;
}

interface TimelineData {
  bucket: string;
  series: TimelineSeries[];
  rolling_7day_avg: Array<{ date: string; win_rate: number }>;
}

interface CondBucket {
  bucket: string;
  n: number;
  wins: number;
  win_rate: number;
}

interface ConditionalData {
  by_trap: CondBucket[];
  by_iv_rank: CondBucket[];
  by_readiness: CondBucket[];
  by_regime: CondBucket[];
}

interface SignalRecord {
  signal_id: string;
  fired_at: string;
  symbol: string;
  signal_type: string;
  bias?: string;
  entry_underlying?: number;
  stop_underlying?: number;
  target_1?: number;
  rr_t1?: number;
  outcome: string;
  pnl_pts?: number;
  time_to_outcome_seconds?: number;
  trap_at_fire?: number;
  iv_rank_at_fire?: number;
  regime_at_fire?: string;
  readiness_at_fire?: number;
}

interface RawData {
  total: number;
  offset: number;
  limit: number;
  records: SignalRecord[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function outcomePill(outcome: string) {
  const upper = outcome?.toUpperCase();
  if (upper === "WIN") return <span className="la-win-pill">WIN</span>;
  if (upper === "BIG_WIN") return <span className="la-win-pill">BIG WIN</span>;
  if (upper === "LOSS") return <span className="la-loss-pill">LOSS</span>;
  return <span className="la-neutral-pill">{outcome}</span>;
}

function winRateColor(wr: number) {
  if (wr >= 0.6) return "#36b37e";
  if (wr >= 0.45) return "#f0b429";
  return "#f05050";
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

function exportCsv(records: SignalRecord[]) {
  const cols: (keyof SignalRecord)[] = [
    "fired_at", "signal_type", "bias", "entry_underlying", "stop_underlying",
    "target_1", "rr_t1", "outcome", "pnl_pts", "time_to_outcome_seconds",
    "trap_at_fire", "iv_rank_at_fire", "regime_at_fire", "readiness_at_fire",
  ];
  const header = cols.join(",");
  const rows = records.map((r) =>
    cols.map((c) => {
      const v = r[c];
      if (v === null || v === undefined) return "";
      const s = String(v);
      return s.includes(",") ? `"${s}"` : s;
    }).join(",")
  );
  const blob = new Blob([header + "\n" + rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `signals_export_${todayStr()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── SubComponents ─────────────────────────────────────────────────────────────

function HeroTiles({ data }: { data: SummaryData }) {
  const wr = data.win_rate;
  return (
    <div className="la-hero">
      <div className="la-hero-tile">
        <div className="la-hero-tile-label">Total Signals</div>
        <div className="la-hero-tile-value">{data.total_signals}</div>
        <div className="la-hero-tile-sub">{data.signals_per_day}/day avg</div>
      </div>
      <div className="la-hero-tile">
        <div className="la-hero-tile-label">Win Rate</div>
        <div className="la-hero-tile-value" style={{ color: winRateColor(wr) }}>{pct(wr)}</div>
        <div className="la-hero-tile-sub">edge {data.net_edge >= 0 ? "+" : ""}{(data.net_edge * 100).toFixed(1)}%</div>
      </div>
      <div className="la-hero-tile">
        <div className="la-hero-tile-label">W / BW / L</div>
        <div className="la-hero-tile-value win">{data.wins}</div>
        <div className="la-hero-tile-sub">{data.big_wins} big wins · {data.losses} losses</div>
      </div>
      <div className="la-hero-tile">
        <div className="la-hero-tile-label">Avg RR Realized</div>
        <div className="la-hero-tile-value neutral">{data.avg_rr_realized ?? "—"}</div>
        <div className="la-hero-tile-sub">predicted {data.avg_rr_predicted ?? "—"}</div>
      </div>
      <div className="la-hero-tile">
        <div className="la-hero-tile-label">Expired</div>
        <div className="la-hero-tile-value">{data.expired}</div>
        <div className="la-hero-tile-sub">{data.total_signals > 0 ? pct(data.expired / data.total_signals) : "—"} of total</div>
      </div>
    </div>
  );
}

function WinRateTrend({ data }: { data: TimelineData }) {
  const option = useMemo(() => {
    const dates = data.series.map((s) => s.date);
    const wrs = data.series.map((s) => +(s.win_rate * 100).toFixed(1));
    const rollDates = data.rolling_7day_avg.map((r) => r.date);
    const rollWrs = data.rolling_7day_avg.map((r) => +(r.win_rate * 100).toFixed(1));
    return {
      backgroundColor: "transparent",
      grid: { top: 16, right: 12, bottom: 40, left: 44, containLabel: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#0d1a27",
        borderColor: "rgba(100,140,180,0.3)",
        textStyle: { color: "#c8d8ec", fontSize: 12 },
        formatter: (params: unknown[]) => {
          const p = params as Array<{ name: string; seriesName: string; value: number; color: string }>;
          return p.map((x) => `<span style="color:${x.color}">●</span> ${x.seriesName}: <b>${x.value}%</b>`).join("<br/>");
        },
      },
      legend: {
        data: ["Daily WR", "7-day Avg"],
        textStyle: { color: "#6b7e94", fontSize: 11 },
        bottom: 0,
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: "#4e6880", fontSize: 10, rotate: 35 },
        axisLine: { lineStyle: { color: "rgba(100,140,180,0.15)" } },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: "#4e6880", fontSize: 10, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "rgba(100,140,180,0.08)" } },
      },
      series: [
        {
          name: "Daily WR",
          type: "bar",
          data: wrs,
          barMaxWidth: 18,
          itemStyle: { color: "#64a0f0", borderRadius: [3, 3, 0, 0] },
        },
        {
          name: "7-day Avg",
          type: "line",
          data: rollDates.map((d) => {
            const idx = dates.indexOf(d);
            return idx >= 0 ? rollWrs[rollDates.indexOf(d)] : null;
          }),
          smooth: true,
          lineStyle: { color: "#f0b429", width: 2 },
          itemStyle: { color: "#f0b429" },
          symbol: "none",
        },
      ],
    };
  }, [data]);

  if (!data.series.length) return <div className="la-empty">No data for this range</div>;
  return <ReactECharts option={option} style={{ height: 220 }} />;
}

function BreakdownTable({ data }: { data: SummaryData }) {
  const [sortKey, setSortKey] = useState<"n" | "win_rate" | "avg_rr">("n");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    return [...data.by_signal_type].sort((a, b) => {
      const av = sortKey === "avg_rr" ? (a.avg_rr ?? -999) : a[sortKey];
      const bv = sortKey === "avg_rr" ? (b.avg_rr ?? -999) : b[sortKey];
      return sortAsc ? av - bv : bv - av;
    });
  }, [data.by_signal_type, sortKey, sortAsc]);

  function toggleSort(k: typeof sortKey) {
    if (k === sortKey) setSortAsc((v) => !v);
    else { setSortKey(k); setSortAsc(false); }
  }

  const arrow = (k: typeof sortKey) => sortKey === k ? (sortAsc ? " ↑" : " ↓") : "";

  return (
    <table className="la-table">
      <thead>
        <tr>
          <th>Signal Type</th>
          <th onClick={() => toggleSort("n")}>Count{arrow("n")}</th>
          <th>W / L</th>
          <th onClick={() => toggleSort("win_rate")}>Win Rate{arrow("win_rate")}</th>
          <th onClick={() => toggleSort("avg_rr")}>Avg RR{arrow("avg_rr")}</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.signal_type}>
            <td style={{ color: "#c8d8ec" }}>{row.signal_type}</td>
            <td>{row.n}</td>
            <td style={{ color: "#36b37e" }}>{row.wins} / <span style={{ color: "#f05050" }}>{row.n - row.wins}</span></td>
            <td style={{ color: winRateColor(row.win_rate), fontWeight: 700 }}>{pct(row.win_rate)}</td>
            <td>{row.avg_rr ?? "—"}</td>
          </tr>
        ))}
        {!sorted.length && (
          <tr><td colSpan={5} className="la-empty">No data</td></tr>
        )}
      </tbody>
    </table>
  );
}

function CondBars({ title, buckets }: { title: string; buckets: CondBucket[] }) {
  return (
    <div>
      <div className="la-panel-title">{title}</div>
      {buckets.map((b) => (
        <div key={b.bucket} className="la-cond-bar-wrap">
          <span className="la-cond-bar-label">{b.bucket}</span>
          <div className="la-cond-bar-track">
            <div
              className="la-cond-bar-fill"
              style={{ width: `${(b.win_rate * 100).toFixed(0)}%`, background: winRateColor(b.win_rate) }}
            />
          </div>
          <span className="la-cond-bar-pct">{pct(b.win_rate)}</span>
          <span className="la-cond-bar-n">n={b.n}</span>
        </div>
      ))}
      {!buckets.length && <div className="la-empty">No data</div>}
    </div>
  );
}

function RecentSignalsTable({
  data, onPageChange, page, pageSize,
}: {
  data: RawData;
  onPageChange: (p: number) => void;
  page: number;
  pageSize: number;
}) {
  const totalPages = Math.ceil(data.total / pageSize);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: "#4e6880" }}>{data.total} total signals</div>
        <button className="la-csv-btn" onClick={() => exportCsv(data.records)}>
          Export CSV
        </button>
      </div>
      <table className="la-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th>Bias</th>
            <th>Entry</th>
            <th>Stop</th>
            <th>T1</th>
            <th>RR</th>
            <th>Outcome</th>
            <th>PnL pts</th>
            <th>Trap</th>
            <th>IVR</th>
            <th>Readiness</th>
            <th>Regime</th>
          </tr>
        </thead>
        <tbody>
          {data.records.map((r) => (
            <tr key={r.signal_id}>
              <td style={{ color: "#4e6880" }}>{r.fired_at?.slice(11, 16) ?? "—"}<br /><span style={{ fontSize: 10 }}>{r.fired_at?.slice(0, 10)}</span></td>
              <td style={{ color: "#c8d8ec", fontSize: 11 }}>{r.signal_type}</td>
              <td style={{ color: r.bias === "BULLISH" ? "#36b37e" : r.bias === "BEARISH" ? "#f05050" : "#4e6880", fontSize: 11 }}>{r.bias ?? "—"}</td>
              <td>{r.entry_underlying?.toFixed(0) ?? "—"}</td>
              <td style={{ color: "#f05050" }}>{r.stop_underlying?.toFixed(0) ?? "—"}</td>
              <td style={{ color: "#36b37e" }}>{r.target_1?.toFixed(0) ?? "—"}</td>
              <td>{r.rr_t1?.toFixed(2) ?? "—"}</td>
              <td>{outcomePill(r.outcome)}</td>
              <td style={{ color: (r.pnl_pts ?? 0) >= 0 ? "#36b37e" : "#f05050" }}>{r.pnl_pts?.toFixed(1) ?? "—"}</td>
              <td>{r.trap_at_fire ?? "—"}</td>
              <td>{r.iv_rank_at_fire?.toFixed(0) ?? "—"}</td>
              <td>{r.readiness_at_fire?.toFixed(0) ?? "—"}</td>
              <td style={{ fontSize: 10, color: "#4e6880" }}>{r.regime_at_fire || "—"}</td>
            </tr>
          ))}
          {!data.records.length && (
            <tr><td colSpan={13} className="la-empty">No signals in range</td></tr>
          )}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="la-pagination">
          <button className="la-page-btn" disabled={page === 0} onClick={() => onPageChange(page - 1)}>← Prev</button>
          <span>{page + 1} / {totalPages}</span>
          <button className="la-page-btn" disabled={page >= totalPages - 1} onClick={() => onPageChange(page + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function LocalAnalytics() {
  const [fromDate, setFromDate] = useState(daysAgo(30));
  const [toDate, setToDate] = useState(todayStr());
  const [symbol, setSymbol] = useState("NIFTY");
  const [signalType, setSignalType] = useState("");

  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [conditional, setConditional] = useState<ConditionalData | null>(null);
  const [rawData, setRawData] = useState<RawData | null>(null);

  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [loadingConditional, setLoadingConditional] = useState(false);
  const [loadingRaw, setLoadingRaw] = useState(false);

  const [errorSummary, setErrorSummary] = useState<string | null>(null);
  const [errorRaw, setErrorRaw] = useState<string | null>(null);

  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  const [backfillLoading, setBackfillLoading] = useState(false);
  const [backfillMsg, setBackfillMsg] = useState<string | null>(null);

  const qs = useCallback(
    (extra = "") =>
      `?from=${fromDate}&to=${toDate}&symbol=${symbol}${signalType ? `&signal_type=${signalType}` : ""}${extra}`,
    [fromDate, toDate, symbol, signalType]
  );

  const fetchAll = useCallback(async () => {
    setPage(0);
    setErrorSummary(null);
    setErrorRaw(null);

    setLoadingSummary(true);
    setLoadingTimeline(true);
    setLoadingConditional(true);
    setLoadingRaw(true);

    const [sum, tl, cond, raw] = await Promise.allSettled([
      apiFetch<SummaryData>(`/performance/summary${qs()}`),
      apiFetch<TimelineData>(`/performance/timeline${qs()}`),
      apiFetch<ConditionalData>(`/performance/conditional${qs()}`),
      apiFetch<RawData>(`/signals/raw${qs(`&limit=${PAGE_SIZE}&offset=0`)}`),
    ]);

    setLoadingSummary(false);
    setLoadingTimeline(false);
    setLoadingConditional(false);
    setLoadingRaw(false);

    if (sum.status === "fulfilled") setSummary(sum.value);
    else setErrorSummary(String((sum as PromiseRejectedResult).reason));
    if (tl.status === "fulfilled") setTimeline(tl.value);
    if (cond.status === "fulfilled") setConditional(cond.value);
    if (raw.status === "fulfilled") setRawData(raw.value);
    else setErrorRaw(String((raw as PromiseRejectedResult).reason));
  }, [qs]);

  useEffect(() => { void fetchAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchRawPage = useCallback(async (p: number) => {
    setLoadingRaw(true);
    setPage(p);
    try {
      const data = await apiFetch<RawData>(
        `/signals/raw${qs(`&limit=${PAGE_SIZE}&offset=${p * PAGE_SIZE}`)}`
      );
      setRawData(data);
    } catch (e) {
      setErrorRaw(String(e));
    } finally {
      setLoadingRaw(false);
    }
  }, [qs]);

  const handleBackfill = async () => {
    setBackfillLoading(true);
    setBackfillMsg(null);
    try {
      const result = await fetch(`${BASE}/debug/backfill-outcomes?symbol=${symbol}`, { method: "POST" });
      const json = await result.json() as { days_processed: number; signals_resolved: number; errors: string[] };
      setBackfillMsg(`Backfill done — ${json.days_processed} days, ${json.signals_resolved} signals. Errors: ${json.errors.length}`);
      void fetchAll();
    } catch (e) {
      setBackfillMsg(`Backfill failed: ${String(e)}`);
    } finally {
      setBackfillLoading(false);
    }
  };

  return (
    <div className="la-root">
      {/* Header */}
      <div className="la-header">
        <span className="la-title">Engine Analytics</span>
        <span className="la-badge-dev">DEV ONLY</span>
        <a href="/app" style={{ fontSize: 12, color: "#4e6880", marginLeft: "auto", textDecoration: "none" }}>← Back to App</a>
      </div>

      {/* Filters */}
      <div className="la-filters">
        <span className="la-filter-label">FROM</span>
        <input className="la-filter-input" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        <span className="la-filter-label">TO</span>
        <input className="la-filter-input" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        <span className="la-filter-label">SYMBOL</span>
        <select className="la-filter-select" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          <option>NIFTY</option>
          <option>BANKNIFTY</option>
          <option>FINNIFTY</option>
        </select>
        <span className="la-filter-label">TYPE</span>
        <input className="la-filter-input" placeholder="all" value={signalType} onChange={(e) => setSignalType(e.target.value)} style={{ width: 120 }} />
        <button className="la-filter-btn" onClick={fetchAll}>Apply</button>
        <button
          className="la-filter-btn la-filter-btn-danger"
          onClick={handleBackfill}
          disabled={backfillLoading}
          title="Compute outcomes for all dates missing outcome files"
        >
          {backfillLoading ? "Backfilling…" : "Backfill Outcomes"}
        </button>
        {backfillMsg && <span style={{ fontSize: 11, color: "#4e6880" }}>{backfillMsg}</span>}
      </div>

      {/* Summary */}
      {errorSummary && <div className="la-error">Could not load summary: {errorSummary}</div>}
      {loadingSummary && <div className="la-loading">Loading summary…</div>}
      {summary && !loadingSummary && <HeroTiles data={summary} />}

      {/* Win Rate Trend */}
      <div className="la-section-title">Win Rate Trend</div>
      <div className="la-row la-row-1">
        <div className="la-panel">
          {loadingTimeline && <div className="la-loading">Loading…</div>}
          {timeline && !loadingTimeline && <WinRateTrend data={timeline} />}
        </div>
      </div>

      {/* Signal Breakdown + Conditional */}
      <div className="la-section-title">Signal Breakdown</div>
      <div className="la-row la-row-2">
        <div className="la-panel">
          <div className="la-panel-title">By Signal Type</div>
          {summary && !loadingSummary && <BreakdownTable data={summary} />}
          {loadingSummary && <div className="la-loading">Loading…</div>}
        </div>
        <div className="la-panel">
          <div className="la-panel-title">Conditional Win Rates</div>
          {loadingConditional && <div className="la-loading">Loading…</div>}
          {conditional && !loadingConditional && (
            <div style={{ display: "grid", gap: 20 }}>
              <CondBars title="By Trap Score" buckets={conditional.by_trap} />
              <CondBars title="By IV Rank" buckets={conditional.by_iv_rank} />
              <CondBars title="By Readiness" buckets={conditional.by_readiness} />
              <CondBars title="By Regime" buckets={conditional.by_regime} />
            </div>
          )}
        </div>
      </div>

      {/* Recent Signals */}
      <div className="la-section-title">Recent Signals</div>
      <div className="la-row la-row-1">
        <div className="la-panel" style={{ overflowX: "auto" }}>
          {errorRaw && <div className="la-error">{errorRaw}</div>}
          {loadingRaw && <div className="la-loading">Loading…</div>}
          {rawData && !loadingRaw && (
            <RecentSignalsTable
              data={rawData}
              page={page}
              pageSize={PAGE_SIZE}
              onPageChange={fetchRawPage}
            />
          )}
        </div>
      </div>
    </div>
  );
}
