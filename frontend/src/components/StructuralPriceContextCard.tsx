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
  supportDefenseRatio?: number | null;
  resistanceDefenseRatio?: number | null;
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

  const trackSummary = useMemo(() => {
    if (!rangeSummary) return null;

    const hasBrokenSupport =
      typeof rangeSummary.previousSupport === "number" &&
      rangeSummary.previousSupport > rangeSummary.support &&
      rangeSummary.spot < rangeSummary.previousSupport;
    const hasBrokenResistance =
      typeof rangeSummary.previousResistance === "number" &&
      rangeSummary.previousResistance < rangeSummary.resistance &&
      rangeSummary.spot > rangeSummary.previousResistance;

    const baseSupport =
      hasBrokenSupport && typeof rangeSummary.previousSupport === "number"
        ? rangeSummary.previousSupport
        : rangeSummary.support;
    const baseResistance =
      hasBrokenResistance && typeof rangeSummary.previousResistance === "number"
        ? rangeSummary.previousResistance
        : rangeSummary.resistance;
    const baseBandWidth = Math.max(1, baseResistance - baseSupport);
    const maxExtension = baseBandWidth * 0.5;

    const leftExtension = Math.min(
      hasBrokenSupport && typeof rangeSummary.previousSupport === "number"
        ? Math.max(0, rangeSummary.previousSupport - rangeSummary.support)
        : 0,
      maxExtension,
    );
    const rightExtension = Math.min(
      hasBrokenResistance && typeof rangeSummary.previousResistance === "number"
        ? Math.max(0, rangeSummary.resistance - rangeSummary.previousResistance)
        : 0,
      maxExtension,
    );
    const totalWidth = leftExtension + baseBandWidth + rightExtension;

    let spotOffset = leftExtension + (rangeSummary.spot - baseSupport);
    if (hasBrokenSupport && typeof rangeSummary.previousSupport === "number") {
      const extensionSpan = Math.max(1, rangeSummary.previousSupport - rangeSummary.support);
      const ratio = (rangeSummary.spot - rangeSummary.support) / extensionSpan;
      spotOffset = leftExtension * Math.max(0, Math.min(1, ratio));
    } else if (hasBrokenResistance && typeof rangeSummary.previousResistance === "number") {
      const extensionSpan = Math.max(1, rangeSummary.resistance - rangeSummary.previousResistance);
      const ratio = (rangeSummary.spot - rangeSummary.previousResistance) / extensionSpan;
      spotOffset = leftExtension + baseBandWidth + (rightExtension * Math.max(0, Math.min(1, ratio)));
    }
    spotOffset = Math.max(0, Math.min(totalWidth, spotOffset));

    const spotPct = (spotOffset / totalWidth) * 100;
    const leftExtensionPct = (leftExtension / totalWidth) * 100;
    const rightExtensionPct = (rightExtension / totalWidth) * 100;
    const bandStartPct = leftExtensionPct;
    const bandWidthPct = (baseBandWidth / totalWidth) * 100;

    let positionText = `${Math.round(((rangeSummary.spot - baseSupport) / baseBandWidth) * 100)}% in band`;
    let metaText = `${Math.round(rangeSummary.distToSupport)} pts above support`;
    let footCenterText = `${Math.round(rangeSummary.distToSupport)} pts above S`;
    let footRightText = `${Math.round(rangeSummary.distToResistance)} pts below R`;

    if (hasBrokenSupport && typeof rangeSummary.previousSupport === "number") {
      positionText = `${Math.round(((rangeSummary.spot - rangeSummary.previousSupport) / baseBandWidth) * 100)}% (breach zone)`;
      metaText = `${Math.round(rangeSummary.previousSupport - rangeSummary.spot)} pts below support`;
      footCenterText = `${Math.round(rangeSummary.previousSupport - rangeSummary.spot)} pts below old S`;
      footRightText = `${Math.round(rangeSummary.resistance - rangeSummary.spot)} pts below R`;
    } else if (hasBrokenResistance && typeof rangeSummary.previousResistance === "number") {
      positionText = `${Math.round(((rangeSummary.spot - rangeSummary.support) / baseBandWidth) * 100)}% (above R)`;
      metaText = `${Math.round(rangeSummary.spot - rangeSummary.previousResistance)} pts above resistance`;
      footCenterText = `${Math.round(rangeSummary.spot - rangeSummary.previousResistance)} pts above old R`;
      footRightText = `${Math.round(rangeSummary.resistance - rangeSummary.spot)} pts below new R`;
    }

    return {
      ...rangeSummary,
      hasBrokenSupport,
      hasBrokenResistance,
      baseBandWidth,
      spotPct,
      leftExtensionPct,
      rightExtensionPct,
      bandStartPct,
      bandWidthPct,
      positionText,
      metaText,
      footCenterText,
      footRightText,
      markerPosition:
        hasBrokenSupport
          ? bandStartPct
          : hasBrokenResistance
            ? bandStartPct + bandWidthPct
            : null,
      markerLabel:
        hasBrokenSupport && typeof rangeSummary.previousSupport === "number"
          ? `old S ${rangeSummary.previousSupport.toLocaleString("en-IN")}`
          : hasBrokenResistance && typeof rangeSummary.previousResistance === "number"
            ? `old R ${rangeSummary.previousResistance.toLocaleString("en-IN")}`
            : null,
    };
  }, [rangeSummary]);

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
        {trackSummary ? (
          <>
            <div className="spc-compact-head">
              <div className="spc-compact-metric">
                <span>Support</span>
                <strong>{trackSummary.support.toLocaleString("en-IN")}</strong>
                {typeof props.supportDefenseRatio === "number" ? (
                  <em className="spc-compact-defense">
                    <span className={`spc-defense-dot ${props.supportDefenseRatio >= 1.0 ? "spc-defense-dot-green" : "spc-defense-dot-red"}`} />
                    PE/CE {props.supportDefenseRatio.toFixed(2)}x
                  </em>
                ) : null}
              </div>
              <div className="spc-compact-metric spc-compact-metric-spot">
                <span>Spot</span>
                <strong>{trackSummary.spot.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong>
              </div>
              <div className="spc-compact-metric">
                <span>Resistance</span>
                <strong>{trackSummary.resistance.toLocaleString("en-IN")}</strong>
                {typeof props.resistanceDefenseRatio === "number" ? (
                  <em className="spc-compact-defense">
                    <span className={`spc-defense-dot ${props.resistanceDefenseRatio >= 1.0 ? "spc-defense-dot-green" : "spc-defense-dot-red"}`} />
                    CE/PE {props.resistanceDefenseRatio.toFixed(2)}x
                  </em>
                ) : null}
              </div>
            </div>
            <div className="spc-range-meta">
              <span className={trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-meta-alert" : undefined}>
                {trackSummary.positionText}
              </span>
              <span className={trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-meta-alert" : undefined}>
                {trackSummary.metaText}
              </span>
              <span>{trackSummary.footRightText}</span>
            </div>
            <div className="spc-range-track">
              <div
                className={`spc-range-extension spc-range-extension-left ${trackSummary.hasBrokenSupport ? "spc-range-extension-active" : ""}`}
                style={{ width: `${trackSummary.leftExtensionPct}%` }}
              />
              <div
                className="spc-range-band"
                style={{
                  left: `${trackSummary.bandStartPct}%`,
                  width: `${trackSummary.bandWidthPct}%`,
                }}
              />
              <div
                className={`spc-range-extension spc-range-extension-right ${trackSummary.hasBrokenResistance ? "spc-range-extension-active" : ""}`}
                style={{ width: `${trackSummary.rightExtensionPct}%` }}
              />
              {trackSummary.markerPosition !== null && trackSummary.markerLabel ? (
                <div className="spc-range-anchor" style={{ left: `${trackSummary.markerPosition}%` }}>
                  <span>{trackSummary.markerLabel}</span>
                </div>
              ) : null}
              <div
                className={`spc-range-spot ${trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-spot-breach" : ""}`}
                style={{ left: `${trackSummary.spotPct}%` }}
              />
            </div>
            <div className="spc-range-foot">
              <span className={trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                {trackSummary.positionText}
              </span>
              <span className={trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                {trackSummary.footCenterText}
              </span>
              <span className={trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                {trackSummary.footRightText}
              </span>
            </div>
            <div className="spc-mini-grid">
              <div className="spc-mini-card">
                <span>Band</span>
                <strong>{Math.round(trackSummary.baseBandWidth)} pts</strong>
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
