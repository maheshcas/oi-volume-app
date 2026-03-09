import { useEffect, useMemo, useRef, useState } from "react";
import {
  AreaSeries,
  CandlestickSeries,
  createChart,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

type OhlcTuple = [string | number, number, number, number, number];
type OhlcPoint = {
  time?: string | number;
  timestamp?: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

type UserTier = "free" | "pro";

type PremiumStructuralChartProps = {
  data: Array<OhlcTuple | OhlcPoint>;
  support: number;
  resistance: number;
  target1: number;
  target2: number;
  trapRisk: number;
  bias: "Bullish" | "Bearish";
  regime: string;
  userTier?: UserTier;
  onUpgradeClick?: () => void;
};

function toEpochSeconds(value: string | number | undefined, idx: number): UTCTimestamp {
  if (typeof value === "number" && Number.isFinite(value)) {
    // If ms epoch, convert ms -> sec.
    const sec = value > 1e12 ? Math.floor(value / 1000) : Math.floor(value);
    return Math.max(1, sec) as UTCTimestamp;
  }
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) {
      return Math.floor(parsed / 1000) as UTCTimestamp;
    }
    const asNum = Number(value);
    if (Number.isFinite(asNum)) {
      const sec = asNum > 1e12 ? Math.floor(asNum / 1000) : Math.floor(asNum);
      return Math.max(1, sec) as UTCTimestamp;
    }
  }
  return Math.floor(Date.now() / 1000) + idx as UTCTimestamp;
}

function normalizeData(raw: Array<OhlcTuple | OhlcPoint>): CandlestickData[] {
  const mapped = raw.map((c, idx) => {
    if (Array.isArray(c)) {
      return {
        time: toEpochSeconds(c[0], idx),
        open: c[1],
        high: c[2],
        low: c[3],
        close: c[4],
      };
    }
    const sourceTs = c.timestamp ?? c.time;
    return {
      time: toEpochSeconds(sourceTs, idx),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    };
  });

  // Lightweight charts requires ascending unique timestamps.
  mapped.sort((a, b) => Number(a.time) - Number(b.time));
  const deduped: CandlestickData[] = [];
  let last = -1;
  for (const row of mapped) {
    const t = Number(row.time);
    if (t === last) continue;
    deduped.push(row);
    last = t;
  }
  return deduped;
}

function aggregateCandlesByMinutes(data: CandlestickData[], minutes: 1 | 5 | 15): CandlestickData[] {
  if (!data.length) return [];
  const bucketSec = minutes * 60;
  const buckets = new Map<number, CandlestickData>();

  for (const candle of data) {
    const ts = Number(candle.time);
    const bucketTs = Math.floor(ts / bucketSec) * bucketSec;
    const existing = buckets.get(bucketTs);
    if (!existing) {
      buckets.set(bucketTs, {
        time: bucketTs as UTCTimestamp,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      });
      continue;
    }
    existing.high = Math.max(existing.high, candle.high);
    existing.low = Math.min(existing.low, candle.low);
    existing.close = candle.close;
  }

  return Array.from(buckets.values()).sort((a, b) => Number(a.time) - Number(b.time));
}

function confidenceLabel(trapRisk: number) {
  const score = 100 - Math.max(0, Math.min(100, trapRisk));
  if (score >= 70) return "Strong";
  if (score >= 50) return "Moderate";
  return "Weak";
}

export default function PremiumStructuralChart(props: PremiumStructuralChartProps) {
  const { data, support, resistance, target1, target2, trapRisk, bias, regime, userTier = "free", onUpgradeClick } = props;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const trapAreaRef = useRef<ISeriesApi<"Area"> | null>(null);
  const lineRefs = useRef<IPriceLine[]>([]);
  const formattedData = useMemo(() => normalizeData(data), [data]);
  const [timeframe, setTimeframe] = useState<"1m" | "5m" | "15m" | "all">("15m");
  const filteredData = useMemo(() => {
    if (!formattedData.length) return [];
    if (timeframe === "all") return formattedData;
    if (timeframe === "1m") return aggregateCandlesByMinutes(formattedData, 1);
    if (timeframe === "5m") return aggregateCandlesByMinutes(formattedData, 5);
    return aggregateCandlesByMinutes(formattedData, 15);
  }, [formattedData, timeframe]);
  const isPro = userTier === "pro";

  // 1) Initialize chart only once.
  useEffect(() => {
    if (!containerRef.current) return;

    chartRef.current = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 520,
      layout: {
        background: { color: "#0b1724" },
        textColor: "#c8d6e5",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)" },
    });

    seriesRef.current = chartRef.current.addSeries(CandlestickSeries, {
      upColor: "#4dd07d",
      downColor: "#ff5c84",
      borderUpColor: "#4dd07d",
      borderDownColor: "#ff5c84",
      wickUpColor: "#4dd07d",
      wickDownColor: "#ff5c84",
    });

    return () => {
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current = null;
      trapAreaRef.current = null;
      lineRefs.current = [];
    };
  }, []);

  // 2) Resize handling.
  useEffect(() => {
    if (!containerRef.current || !chartRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width > 0) chartRef.current?.applyOptions({ width });
    });
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // 3) Data updates only.
  useEffect(() => {
    if (!seriesRef.current || !filteredData.length) return;
    seriesRef.current.setData(filteredData);
    chartRef.current?.timeScale().fitContent();
    // Debug: check sec timestamps.
    // eslint-disable-next-line no-console
    console.log("First Candle:", filteredData?.[0]);
  }, [filteredData]);

  // 4) Structural overlays updates.
  useEffect(() => {
    if (!seriesRef.current) return;
    for (const line of lineRefs.current) {
      seriesRef.current.removePriceLine(line);
    }
    lineRefs.current = [];

    lineRefs.current.push(
      seriesRef.current.createPriceLine({
        price: support,
        color: "#4dd07d",
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Support",
      })
    );

    lineRefs.current.push(
      seriesRef.current.createPriceLine({
        price: resistance,
        color: "#ff5c84",
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Resistance",
      })
    );

    lineRefs.current.push(
      seriesRef.current.createPriceLine({
        price: target1,
        color: "#63b5ff",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "Target 1",
      })
    );

    lineRefs.current.push(
      seriesRef.current.createPriceLine({
        price: target2,
        color: "#63b5ff",
        lineWidth: 2,
        lineStyle: 1,
        axisLabelVisible: true,
        title: "Target 2",
      })
    );
  }, [support, resistance, target1, target2]);

  // 5) Trap area shading.
  useEffect(() => {
    if (!chartRef.current || !filteredData.length) return;

    if (trapAreaRef.current) {
      chartRef.current.removeSeries(trapAreaRef.current);
      trapAreaRef.current = null;
    }

    if (trapRisk > 50) {
      trapAreaRef.current = chartRef.current.addSeries(AreaSeries, {
        lineColor: "rgba(0,0,0,0)",
        topColor: bias === "Bearish" ? "rgba(255,92,132,0.18)" : "rgba(77,208,125,0.18)",
        bottomColor: "rgba(0,0,0,0)",
        lineWidth: 1,
      });
      const trapLevel = bias === "Bearish" ? resistance : support;
      trapAreaRef.current.setData(filteredData.map((row) => ({ time: row.time, value: trapLevel })));
    }
  }, [trapRisk, bias, support, resistance, filteredData]);

  return (
    <div className={`premium-shell ${isPro ? "premium-pro" : "premium-free"}`}>
      <div className="premium-topbar">
        <span className="premium-head">
          Bias: <b className={bias === "Bullish" ? "premium-bull" : "premium-bear"}>{bias} ({confidenceLabel(trapRisk)})</b>
          <span className="premium-sep">|</span>
          Regime: <b className="premium-regime">{regime}</b>
        </span>
        <div className="premium-timeframes">
          {(["1m", "5m", "15m", "all"] as const).map((tf) => (
            <button
              key={tf}
              type="button"
              className={`premium-tf-btn ${timeframe === tf ? "active" : ""}`}
              onClick={() => setTimeframe(tf)}
            >
              {tf.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="premium-title">Structural Price Context</div>
      <div className={`premium-chart-wrap ${isPro ? "" : "premium-chart-wrap-locked"}`}>
        <div ref={containerRef} style={{ width: "100%", height: "520px" }} />
      </div>
      {!isPro ? <div className="premium-hover-tease">Structural overlays unlocked in Pro</div> : null}
      {!isPro ? (
        <div className="premium-overlay">
          <div className="premium-overlay-panel">
            <h3 className="premium-overlay-title">Premium Feature – Structural Price Context</h3>
            <p className="premium-overlay-sub">See structure in price, not just numbers.</p>
            <button type="button" onClick={onUpgradeClick} className="premium-upgrade-btn">
              Upgrade to Pro
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
