import { useMemo } from "react";
import SingleStructureCandleCard from "./SingleStructureCandleCard";

type CandlePoint = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

type StructuralPriceContextCardProps = {
  candles: CandlePoint[];
  spotPrice: number | null;
  dayOpen?: number | null;
  dayHigh?: number | null;
  dayLow?: number | null;
  supportLevel?: number | null;
  resistanceLevel?: number | null;
  supportStart: number | null;
  supportEnd: number | null;
  resistanceStart: number | null;
  resistanceEnd: number | null;
  target1: number | null;
  target2: number | null;
  bias: string;
  biasStrength: string;
  regime: string;
  showPremiumOverlay?: boolean;
  trapZoneLabel?: string;
  volumeLabel?: string;
};

function dayKey(ms: number) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(ms));
}

export default function StructuralPriceContextCard(props: StructuralPriceContextCardProps) {
  const todayCandles = useMemo(() => {
    if (!props.candles.length) return [] as CandlePoint[];
    const today = dayKey(Date.now());
    const set = props.candles.filter((c) => dayKey(c.time) === today);
    if (set.length) return set;
    const latest = props.candles[props.candles.length - 1];
    return props.candles.filter((c) => dayKey(c.time) === dayKey(latest.time));
  }, [props.candles]);

  const ohlc = useMemo(() => {
    if (todayCandles.length) {
      const open = props.dayOpen ?? todayCandles[0].open;
      const high = props.dayHigh ?? Math.max(...todayCandles.map((c) => c.high));
      const low = props.dayLow ?? Math.min(...todayCandles.map((c) => c.low));
      const close = todayCandles[todayCandles.length - 1].close;
      return { open, high, low, close };
    }
    if (
      props.dayOpen !== null &&
      props.dayOpen !== undefined &&
      props.dayHigh !== null &&
      props.dayHigh !== undefined &&
      props.dayLow !== null &&
      props.dayLow !== undefined &&
      props.spotPrice !== null
    ) {
      return { open: props.dayOpen, high: props.dayHigh, low: props.dayLow, close: props.spotPrice };
    }
    return null;
  }, [props.dayHigh, props.dayLow, props.dayOpen, props.spotPrice, todayCandles]);

  return (
    <div className="spc-card">
      <div className="spc-status-row">
        <span>
          Bias: <strong>{props.bias}</strong> ({props.biasStrength})
        </span>
        <span className="spc-divider">|</span>
        <span>
          Regime: <strong>{props.regime}</strong>
        </span>
      </div>
      <div className="spc-title">Structural Price Context</div>
      <div className="spc-chart-wrap">
        {ohlc && props.spotPrice !== null ? (
          <SingleStructureCandleCard
            open={ohlc.open}
            high={ohlc.high}
            low={ohlc.low}
            close={ohlc.close}
            spot={props.spotPrice}
            title="Structural Session Candle"
            subtitle={props.trapZoneLabel ? `Trap Zone: ${props.trapZoneLabel}` : undefined}
            bias={`${props.bias} (${props.biasStrength})`}
            regime={props.regime}
            support={props.supportLevel ?? null}
            resistance={props.resistanceLevel ?? null}
            supportStart={props.supportStart}
            supportEnd={props.supportEnd}
            resistanceStart={props.resistanceStart}
            resistanceEnd={props.resistanceEnd}
            target1={props.target1}
            target2={props.target2}
            height={320}
          />
        ) : (
          <div className="spc-empty">Waiting for today OHLC data...</div>
        )}
        {props.showPremiumOverlay ? (
          <div className="spc-overlay">
            <div className="spc-overlay-panel">
              <h4>Premium Feature - Structural Price Context</h4>
              <p>See structure in price, not just numbers.</p>
              <button type="button">Upgrade to Pro</button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
