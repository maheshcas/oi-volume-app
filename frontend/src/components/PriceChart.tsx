import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

type CandleInput = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

type PriceChartProps = {
  candles: CandleInput[];
  spot: number | null;
  support: number | null;
  resistance: number | null;
  supportRange?: [number | null, number | null] | null;
  resistanceRange?: [number | null, number | null] | null;
  supportPressureState?: string;
  resistancePressureState?: string;
  target1: number | null;
  target2: number | null;
};

function normalizeCandles(data: CandleInput[]): Array<{
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
}> {
  const out = data
    .map((c) => ({
      time: Math.floor(c.time) as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    .sort((a, b) => Number(a.time) - Number(b.time));
  const dedup: typeof out = [];
  let prev = -1;
  for (const c of out) {
    const t = Number(c.time);
    if (t === prev) continue;
    dedup.push(c);
    prev = t;
  }
  return dedup;
}

function aggregateCandles(
  data: Array<{ time: UTCTimestamp; open: number; high: number; low: number; close: number }>,
  minutes: 1 | 5 | 15
) {
  if (!data.length) return [];
  const bucketSec = minutes * 60;
  const buckets = new Map<number, { time: UTCTimestamp; open: number; high: number; low: number; close: number }>();
  for (const candle of data) {
    const ts = Number(candle.time);
    const key = Math.floor(ts / bucketSec) * bucketSec;
    const prev = buckets.get(key);
    if (!prev) {
      buckets.set(key, {
        time: key as UTCTimestamp,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      });
      continue;
    }
    prev.high = Math.max(prev.high, candle.high);
    prev.low = Math.min(prev.low, candle.low);
    prev.close = candle.close;
  }
  return Array.from(buckets.values()).sort((a, b) => Number(a.time) - Number(b.time));
}

export default function PriceChart(props: PriceChartProps) {
  const [timeframe, setTimeframe] = useState<"1m" | "5m" | "15m">("5m");
  const [tooltip, setTooltip] = useState<string>("");
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lineRefs = useRef<IPriceLine[]>([]);
  const [zones, setZones] = useState<{
    supportTop: number | null;
    supportBottom: number | null;
    resistanceTop: number | null;
    resistanceBottom: number | null;
    supportLabelY: number | null;
    resistanceLabelY: number | null;
  }>({
    supportTop: null,
    supportBottom: null,
    resistanceTop: null,
    resistanceBottom: null,
    supportLabelY: null,
    resistanceLabelY: null,
  });

  const candles = useMemo(() => {
    const normalized = normalizeCandles(props.candles);
    if (!normalized.length) return [];
    if (timeframe === "1m") return aggregateCandles(normalized, 1);
    if (timeframe === "5m") return aggregateCandles(normalized, 5);
    return aggregateCandles(normalized, 15);
  }, [props.candles, timeframe]);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 420,
      layout: {
        background: { color: "#0f172a" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      rightPriceScale: {
        borderColor: "#374151",
      },
      timeScale: {
        borderColor: "#374151",
      },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#4dd07d",
      downColor: "#ff5c84",
      borderUpColor: "#4dd07d",
      borderDownColor: "#ff5c84",
      wickUpColor: "#4dd07d",
      wickDownColor: "#ff5c84",
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver(() => {
      if (!chartContainerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      requestAnimationFrame(() => updateZones());
    });
    resizeObserver.observe(chartContainerRef.current);

    const moveHandler = (event: MouseEvent) => {
      if (!wrapperRef.current || !seriesRef.current) return;
      const rect = wrapperRef.current.getBoundingClientRect();
      const y = event.clientY - rect.top;
      const near = (val: number | null) => (val === null ? false : Math.abs(y - val) < 12);
      if (near(zones.supportLabelY)) {
        setTooltip(`Support zone | ${props.supportPressureState ?? "Stable"}`);
      } else if (near(zones.resistanceLabelY)) {
        setTooltip(`Resistance zone | ${props.resistancePressureState ?? "Stable"}`);
      } else {
        setTooltip("");
      }
    };
    wrapperRef.current?.addEventListener("mousemove", moveHandler);

    return () => {
      wrapperRef.current?.removeEventListener("mousemove", moveHandler);
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      lineRefs.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateZones = () => {
    const series = seriesRef.current;
    if (!series) return;
    const supportLow = props.supportRange?.[0] ?? null;
    const supportHigh = props.supportRange?.[1] ?? null;
    const resistanceLow = props.resistanceRange?.[0] ?? null;
    const resistanceHigh = props.resistanceRange?.[1] ?? null;

    const supportTop =
      supportHigh !== null && supportHigh !== undefined ? series.priceToCoordinate(supportHigh) ?? null : null;
    const supportBottom =
      supportLow !== null && supportLow !== undefined ? series.priceToCoordinate(supportLow) ?? null : null;
    const resistanceTop =
      resistanceHigh !== null && resistanceHigh !== undefined
        ? series.priceToCoordinate(resistanceHigh) ?? null
        : null;
    const resistanceBottom =
      resistanceLow !== null && resistanceLow !== undefined ? series.priceToCoordinate(resistanceLow) ?? null : null;

    const supportCenter =
      supportLow !== null && supportHigh !== null ? (supportLow + supportHigh) / 2 : props.support ?? null;
    const resistanceCenter =
      resistanceLow !== null && resistanceHigh !== null ? (resistanceLow + resistanceHigh) / 2 : props.resistance ?? null;

    const supportLabelY =
      supportCenter !== null && supportCenter !== undefined ? series.priceToCoordinate(supportCenter) ?? null : null;
    const resistanceLabelY =
      resistanceCenter !== null && resistanceCenter !== undefined
        ? series.priceToCoordinate(resistanceCenter) ?? null
        : null;

    setZones({
      supportTop,
      supportBottom,
      resistanceTop,
      resistanceBottom,
      supportLabelY,
      resistanceLabelY,
    });
  };

  useEffect(() => {
    if (!seriesRef.current || !candles.length) return;
    seriesRef.current.setData(candles);
    chartRef.current?.timeScale().fitContent();
    requestAnimationFrame(() => updateZones());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles]);

  useEffect(() => {
    if (!seriesRef.current) return;
    for (const line of lineRefs.current) {
      seriesRef.current.removePriceLine(line);
    }
    lineRefs.current = [];

    if (props.support !== null) {
      lineRefs.current.push(
        seriesRef.current.createPriceLine({
          price: props.support,
          color: "#22c55e",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "Support",
        })
      );
    }
    if (props.resistance !== null) {
      lineRefs.current.push(
        seriesRef.current.createPriceLine({
          price: props.resistance,
          color: "#ef4444",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "Resistance",
        })
      );
    }
    if (props.target1 !== null) {
      lineRefs.current.push(
        seriesRef.current.createPriceLine({
          price: props.target1,
          color: "#3b82f6",
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "Target",
        })
      );
    }
    if (props.target2 !== null) {
      lineRefs.current.push(
        seriesRef.current.createPriceLine({
          price: props.target2,
          color: "rgba(59,130,246,0.6)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "T2",
        })
      );
    }
    if (props.spot !== null) {
      lineRefs.current.push(
        seriesRef.current.createPriceLine({
          price: props.spot,
          color: "#ffffff",
          lineWidth: 1,
          axisLabelVisible: true,
          title: "SPOT",
        })
      );
    }

    requestAnimationFrame(() => updateZones());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    props.support,
    props.resistance,
    props.target1,
    props.target2,
    props.spot,
    props.supportRange,
    props.resistanceRange,
  ]);

  const renderZone = (top: number | null, bottom: number | null, cls: string) => {
    if (top === null || bottom === null) return null;
    const y = Math.min(top, bottom);
    const h = Math.max(2, Math.abs(bottom - top));
    return <div className={`pc-zone ${cls}`} style={{ top: y, height: h }} />;
  };

  return (
    <div className="price-chart-shell">
      <div className="price-chart-head">
        <div className="price-chart-title">Price Action + Levels</div>
        <div className="price-chart-tfs">
          {(["1m", "5m", "15m"] as const).map((tf) => (
            <button
              key={tf}
              type="button"
              className={`price-chart-tf-btn ${timeframe === tf ? "active" : ""}`}
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      <div className="price-chart-wrap" ref={wrapperRef}>
        <div ref={chartContainerRef} style={{ width: "100%", height: "420px" }} />
        {renderZone(zones.supportTop, zones.supportBottom, "pc-support")}
        {renderZone(zones.resistanceTop, zones.resistanceBottom, "pc-resistance")}
        {zones.supportLabelY !== null ? (
          <div className="pc-label pc-label-support" style={{ top: zones.supportLabelY - 12 }}>
            Support | {props.supportPressureState ?? "Stable"}
          </div>
        ) : null}
        {zones.resistanceLabelY !== null ? (
          <div className="pc-label pc-label-resistance" style={{ top: zones.resistanceLabelY - 12 }}>
            Resistance | {props.resistancePressureState ?? "Stable"}
          </div>
        ) : null}
        {tooltip ? <div className="pc-tooltip">{tooltip}</div> : null}
      </div>
    </div>
  );
}
