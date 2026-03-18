import { useEffect, useMemo, useState } from "react";
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
  previousSupport?: number | null;
  previousResistance?: number | null;
  materialBreachConfirmed?: boolean;
  confirmationType?: string | null;
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
  const [isCompactViewport, setIsCompactViewport] = useState(false);
  const [showChart, setShowChart] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const media = window.matchMedia("(max-width: 900px)");
    const syncViewport = () => {
      const compact = media.matches;
      setIsCompactViewport(compact);
      setShowChart((current) => (compact ? current : true));
    };

    syncViewport();
    media.addEventListener("change", syncViewport);
    return () => media.removeEventListener("change", syncViewport);
  }, []);

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

  const rangeSummary = useMemo(() => {
    if (
      props.spotPrice === null ||
      props.supportLevel === null ||
      props.supportLevel === undefined ||
      props.resistanceLevel === null ||
      props.resistanceLevel === undefined ||
      props.resistanceLevel <= props.supportLevel
    ) {
      return null;
    }

    const position =
      ((props.spotPrice - props.supportLevel) / (props.resistanceLevel - props.supportLevel)) * 100;
    const bandWidth = props.resistanceLevel - props.supportLevel;
    const distToResistance = props.resistanceLevel - props.spotPrice;
    const distToSupport = props.spotPrice - props.supportLevel;
    return {
      support: props.supportLevel,
      resistance: props.resistanceLevel,
      previousSupport:
        typeof props.previousSupport === "number" && props.previousSupport !== props.supportLevel
          ? props.previousSupport
          : null,
      previousResistance:
        typeof props.previousResistance === "number" && props.previousResistance !== props.resistanceLevel
          ? props.previousResistance
          : null,
      spot: props.spotPrice,
      position: Math.max(0, Math.min(100, position)),
      bandWidth,
      distToResistance,
      distToSupport,
    };
  }, [props.previousResistance, props.previousSupport, props.resistanceLevel, props.spotPrice, props.supportLevel]);

  const breachMarkers = useMemo(() => {
    if (!rangeSummary || !props.materialBreachConfirmed) return [] as Array<{
      key: string;
      position: number;
      label: string;
      tone: "amber" | "green" | "red";
    }>;

    const bandWidth = rangeSummary.resistance - rangeSummary.support;
    if (bandWidth <= 0) {
      return [];
    }

    const confirmationType = String(props.confirmationType ?? "").toLowerCase();
    const computePosition = (value: number) =>
      ((value - rangeSummary.support) / bandWidth) * 100;

    const markers = [] as Array<{
      key: string;
      position: number;
      label: string;
      tone: "amber" | "green" | "red";
    }>;

    if (rangeSummary.previousSupport !== null) {
      const supportTone =
        confirmationType.includes("support") || confirmationType.includes("down")
          ? "red"
          : "amber";
      markers.push({
        key: "previous-support",
        position: Math.max(0, Math.min(100, computePosition(rangeSummary.previousSupport))),
        label: `${rangeSummary.previousSupport.toLocaleString("en-IN")} ${supportTone === "red" ? "↓" : ""}`.trim(),
        tone: supportTone,
      });
    }

    if (rangeSummary.previousResistance !== null) {
      const resistanceTone =
        confirmationType.includes("resistance") || confirmationType.includes("breakout")
          ? "green"
          : "amber";
      markers.push({
        key: "previous-resistance",
        position: Math.max(0, Math.min(100, computePosition(rangeSummary.previousResistance))),
        label: `${rangeSummary.previousResistance.toLocaleString("en-IN")} ${resistanceTone === "green" ? "↑" : ""}`.trim(),
        tone: resistanceTone,
      });
    }

    return markers;
  }, [props.confirmationType, props.materialBreachConfirmed, rangeSummary]);

  const compactTargets = useMemo(() => {
    const targets = [
      { key: "target1", value: props.target1, fallbackLabel: "Target 1" },
      { key: "target2", value: props.target2, fallbackLabel: "Target 2" },
    ];
    return targets.map((target) => {
      const value = target.value;
      if (value === null || value === undefined) {
        return { ...target, label: target.fallbackLabel, hint: null };
      }
      if (props.resistanceLevel !== null && props.resistanceLevel !== undefined && value > props.resistanceLevel) {
        return {
          ...target,
          label: "Upside Target",
          hint: `Above ${props.resistanceLevel.toLocaleString("en-IN")}`,
        };
      }
      if (props.supportLevel !== null && props.supportLevel !== undefined && value < props.supportLevel) {
        return {
          ...target,
          label: "Downside Target",
          hint: `Below ${props.supportLevel.toLocaleString("en-IN")}`,
        };
      }
      return { ...target, label: target.fallbackLabel, hint: "Inside band" };
    });
  }, [props.resistanceLevel, props.supportLevel, props.target1, props.target2]);

  return (
    <div className="spc-card">
      <div className="spc-head">
        <div>
          <div className="spc-title">Structural Price Context</div>
          <div className="spc-status-row">
            <span className="spc-chip spc-chip-neutral">
              Bias <strong>{props.bias}</strong>
            </span>
            <span className="spc-chip spc-chip-neutral">
              Regime <strong>{props.regime}</strong>
            </span>
            {props.volumeLabel ? <span className="spc-chip spc-chip-muted">{props.volumeLabel}</span> : null}
          </div>
        </div>
        <button
          type="button"
          className="spc-toggle"
          onClick={() => setShowChart((current) => !current)}
        >
          {showChart ? "Hide Chart" : "Show Chart"}
        </button>
      </div>
      <div className="spc-compact-panel">
        {rangeSummary ? (
          <>
            <div className="spc-compact-head">
              <div className="spc-compact-metric">
                <span>Support</span>
                <strong>{rangeSummary.support.toLocaleString("en-IN")}</strong>
              </div>
              <div className="spc-compact-metric spc-compact-metric-spot">
                <span>Spot</span>
                <strong>{rangeSummary.spot.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="spc-compact-metric">
                <span>Resistance</span>
                <strong>{rangeSummary.resistance.toLocaleString("en-IN")}</strong>
              </div>
            </div>
            <div className="spc-range-meta">
              <span>{Math.round(rangeSummary.position)}% in band</span>
              <span>{Math.round(rangeSummary.distToSupport)} pts above support</span>
              <span>{Math.round(rangeSummary.distToResistance)} pts below resistance</span>
            </div>
            <div className="spc-range-track">
              <div className="spc-range-line" />
              <div className="spc-range-zone spc-range-zone-support" />
              <div className="spc-range-zone spc-range-zone-resistance" />
              {breachMarkers.map((marker) => (
                <div
                  className={`spc-range-marker spc-range-marker-${marker.tone}`}
                  key={marker.key}
                  style={{ left: `${marker.position}%` }}
                >
                  <span>{marker.label}</span>
                </div>
              ))}
              <div className="spc-range-spot" style={{ left: `${rangeSummary.position}%` }} />
            </div>
            <div className="spc-mini-grid">
              <div className="spc-mini-card">
                <span>Band</span>
                <strong>{Math.round(rangeSummary.bandWidth)} pts</strong>
              </div>
              {compactTargets.map((target) => (
                <div className="spc-mini-card" key={target.key}>
                  <span>{target.label}</span>
                  <strong>{target.value !== null && target.value !== undefined ? target.value.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : "-"}</strong>
                  {target.hint ? <em>{target.hint}</em> : null}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="spc-compact-empty">Support, resistance, or spot is not available yet.</div>
        )}
      </div>
      <div className={`spc-chart-wrap ${showChart ? "spc-chart-wrap-open" : "spc-chart-wrap-closed"}`}>
        {showChart ? (ohlc && props.spotPrice !== null ? (
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
            height={isCompactViewport ? 240 : 260}
          />
        ) : (
          <div className="spc-empty">Waiting for today OHLC data...</div>
        )) : null}
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
