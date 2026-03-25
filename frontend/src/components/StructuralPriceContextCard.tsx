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
  sessionPhase?: string | null;
  bias: string;
  biasStrength: string;
  regime: string;
  breakoutProbabilityUp?: number | null;
  breakoutProbabilityDown?: number | null;
  trapProbability?: number | null;
  trapDirection?: "upside" | "downside" | "";
  readinessScore?: number | null;
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

function formatCompactNumber(value: number | null | undefined, digits = 0) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fallbackPercent(value: number | null | undefined, fallback: number) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.min(100, value));
  }
  return Math.max(0, Math.min(100, fallback));
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

    const hasSupportShift =
      typeof rangeSummary.previousSupport === "number" &&
      rangeSummary.previousSupport < rangeSummary.support;
    const hasResistanceShift =
      typeof rangeSummary.previousResistance === "number" &&
      rangeSummary.previousResistance > rangeSummary.resistance;
    const hasBrokenSupport =
      typeof rangeSummary.previousSupport === "number" &&
      rangeSummary.previousSupport > rangeSummary.support &&
      rangeSummary.spot < rangeSummary.previousSupport;
    const hasBrokenResistance =
      typeof rangeSummary.previousResistance === "number" &&
      rangeSummary.previousResistance < rangeSummary.resistance &&
      rangeSummary.spot > rangeSummary.previousResistance;
    const nearSupport =
      rangeSummary.distToSupport >= 0 &&
      rangeSummary.distToSupport < 30 &&
      !hasBrokenSupport &&
      !hasBrokenResistance;
    const nearResistance =
      rangeSummary.distToResistance >= 0 &&
      rangeSummary.distToResistance < 30 &&
      !hasBrokenSupport &&
      !hasBrokenResistance;

    const baseBandWidth = Math.max(1, rangeSummary.resistance - rangeSummary.support);
    const maxExtension = baseBandWidth * 0.5;

    const leftContextDistance =
      (hasBrokenSupport || hasSupportShift) && typeof rangeSummary.previousSupport === "number"
        ? Math.max(0, rangeSummary.previousSupport - rangeSummary.spot)
        : 0;
    const rightContextDistance =
      (hasBrokenResistance || hasResistanceShift) && typeof rangeSummary.previousResistance === "number"
        ? Math.max(0, rangeSummary.spot - rangeSummary.previousResistance)
        : 0;

    const leftShiftDistance =
      hasSupportShift && typeof rangeSummary.previousSupport === "number"
        ? Math.max(0, rangeSummary.support - rangeSummary.previousSupport)
        : 0;
    const rightShiftDistance =
      hasResistanceShift && typeof rangeSummary.previousResistance === "number"
        ? Math.max(0, rangeSummary.previousResistance - rangeSummary.resistance)
        : 0;

    const leftExtension = Math.min(Math.max(leftContextDistance, leftShiftDistance), maxExtension);
    const rightExtension = Math.min(Math.max(rightContextDistance, rightShiftDistance), maxExtension);
    const totalWidth = leftExtension + baseBandWidth + rightExtension;

    let spotOffset = leftExtension + (rangeSummary.spot - rangeSummary.support);
    if (hasBrokenSupport) {
      spotOffset = Math.max(0, leftExtension - leftContextDistance);
    } else if (hasBrokenResistance) {
      spotOffset = Math.min(totalWidth, leftExtension + baseBandWidth + rightContextDistance);
    }
    spotOffset = Math.max(0, Math.min(totalWidth, spotOffset));

    const spotPct = (spotOffset / totalWidth) * 100;
    const leftExtensionPct = (leftExtension / totalWidth) * 100;
    const rightExtensionPct = (rightExtension / totalWidth) * 100;
    const bandStartPct = leftExtensionPct;
    const bandWidthPct = (baseBandWidth / totalWidth) * 100;

    let positionPercent = ((rangeSummary.spot - rangeSummary.support) / baseBandWidth) * 100;
    let positionText = `${Math.round(positionPercent)}% in band`;
    let metaText = `${Math.round(rangeSummary.distToSupport)} pts above support`;
    let footCenterText = `${Math.round(rangeSummary.distToSupport)} pts above S`;
    let footRightText =
      rangeSummary.distToResistance >= 0
        ? `${Math.round(rangeSummary.distToResistance)} pts below R`
        : `${Math.round(Math.abs(rangeSummary.distToResistance))} pts above R`;
    let supportLabel = rangeSummary.support.toLocaleString("en-IN");
    let resistanceLabel = rangeSummary.resistance.toLocaleString("en-IN");

    if (hasBrokenSupport && typeof rangeSummary.previousSupport === "number") {
      positionPercent = ((rangeSummary.spot - rangeSummary.previousSupport) / baseBandWidth) * 100;
      positionText = `${Math.round(positionPercent)}% (breach zone)`;
      metaText = `${Math.round(rangeSummary.previousSupport - rangeSummary.spot)} pts below support`;
      footCenterText = `${Math.round(rangeSummary.previousSupport - rangeSummary.spot)} pts below old S`;
      footRightText =
        rangeSummary.resistance >= rangeSummary.spot
          ? `${Math.round(rangeSummary.resistance - rangeSummary.spot)} pts below R`
          : `${Math.round(rangeSummary.spot - rangeSummary.resistance)} pts above R`;
      supportLabel = `newS ${rangeSummary.support.toLocaleString("en-IN")}`;
    } else if (hasBrokenResistance && typeof rangeSummary.previousResistance === "number") {
      positionPercent = ((rangeSummary.spot - rangeSummary.previousResistance) / baseBandWidth) * 100 + 100;
      positionText = `${Math.round(positionPercent)}% (above R)`;
      metaText = `${Math.round(rangeSummary.spot - rangeSummary.previousResistance)} pts above resistance`;
      footCenterText = `${Math.round(rangeSummary.spot - rangeSummary.previousResistance)} pts above old R`;
      footRightText = `${Math.round(rangeSummary.resistance - rangeSummary.spot)} pts below new R`;
      resistanceLabel = `newR ${rangeSummary.resistance.toLocaleString("en-IN")}`;
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
      positionPercent,
      metaText,
      footCenterText,
      footRightText,
      supportLabel,
      resistanceLabel,
      markerPosition:
        hasBrokenSupport || hasSupportShift
          ? bandStartPct
          : hasBrokenResistance || hasResistanceShift
            ? bandStartPct + bandWidthPct
            : null,
      markerLabel:
        (hasBrokenSupport || hasSupportShift) && typeof rangeSummary.previousSupport === "number"
          ? `old S ${rangeSummary.previousSupport.toLocaleString("en-IN")}`
          : (hasBrokenResistance || hasResistanceShift) && typeof rangeSummary.previousResistance === "number"
            ? `old R ${rangeSummary.previousResistance.toLocaleString("en-IN")}`
            : null,
      nearSupport,
      nearResistance,
      isUpperThird: positionPercent >= 67,
      isLowerThird: positionPercent <= 33,
    };
  }, [rangeSummary]);

  const structuralStateLabel = useMemo(() => {
    if (!trackSummary) return "Inside Balanced Range";
    if (props.materialBreachConfirmed && trackSummary.hasBrokenResistance) return "Resistance Broken";
    if (props.materialBreachConfirmed && trackSummary.hasBrokenSupport) return "Support Broken";
    if ((props.trapProbability ?? 0) >= 40 && props.trapDirection === "downside") return "Resistance Rejection Risk";
    if ((props.trapProbability ?? 0) >= 40 && props.trapDirection === "upside") return "Support Absorption Risk";
    if (trackSummary.isUpperThird) return "Resistance Breakout Watch";
    if (trackSummary.isLowerThird) return "Support Breakdown Watch";
    return "Inside Balanced Range";
  }, [props.materialBreachConfirmed, props.trapDirection, props.trapProbability, trackSummary]);

  const phaseLabel = useMemo(() => {
    const phaseText = String(props.sessionPhase || "").trim();
    return phaseText || "Transition";
  }, [props.sessionPhase]);

  const watchZone = useMemo(() => {
    if (!trackSummary) return null;
    if (trackSummary.hasBrokenSupport || trackSummary.isLowerThird) {
      return {
        left: `${trackSummary.bandStartPct}%`,
        width: `${Math.min(trackSummary.bandWidthPct * 0.22, 22)}%`,
        tone: "support" as const,
      };
    }
    if (trackSummary.hasBrokenResistance || trackSummary.isUpperThird) {
      const widthPct = Math.min(trackSummary.bandWidthPct * 0.22, 22);
      return {
        left: `${trackSummary.bandStartPct + trackSummary.bandWidthPct - widthPct}%`,
        width: `${widthPct}%`,
        tone: "resistance" as const,
      };
    }
    return null;
  }, [trackSummary]);

  const breachBanner = useMemo(() => {
    if (!trackSummary) return null;
    if (trackSummary.hasBrokenSupport) {
      return {
        className: "spc-breach-banner spc-breach-banner-support-break",
        text: `Support broken below ${trackSummary.support.toLocaleString("en-IN")}`,
      };
    }
    if (trackSummary.hasBrokenResistance) {
      return {
        className: "spc-breach-banner spc-breach-banner-resistance-break",
        text: `Resistance broken above ${trackSummary.resistance.toLocaleString("en-IN")}`,
      };
    }
    if (trackSummary.nearSupport) {
      return {
        className: "spc-breach-banner spc-breach-banner-near-s",
        text: `Approaching support at ${trackSummary.support.toLocaleString("en-IN")}`,
      };
    }
    if (trackSummary.nearResistance) {
      return {
        className: "spc-breach-banner spc-breach-banner-near-r",
        text: `Approaching resistance at ${trackSummary.resistance.toLocaleString("en-IN")}`,
      };
    }
    return null;
  }, [trackSummary]);

  const compactRangeTarget = useMemo(() => {
    const targets = [props.target1, props.target2].filter(
      (value): value is number => typeof value === "number" && !Number.isNaN(value)
    );
    if (!targets.length) {
      return { text: "Range -", hint: null as string | null };
    }
    const low = Math.min(...targets);
    const high = Math.max(...targets);
    let hint = "Inside structure envelope";
    if (
      props.supportLevel !== null &&
      props.supportLevel !== undefined &&
      props.resistanceLevel !== null &&
      props.resistanceLevel !== undefined
    ) {
      hint = `Below ${props.supportLevel.toLocaleString("en-IN")} · Above ${props.resistanceLevel.toLocaleString("en-IN")}`;
    }
    return {
      text: `${low.toLocaleString("en-IN", { maximumFractionDigits: 0 })} ↔ ${high.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`,
      hint,
    };
  }, [props.resistanceLevel, props.supportLevel, props.target1, props.target2]);

  const compactTargets: Array<{ key: string; label: string; value: number | null; hint: string | null }> = [];

  const previousSupportLabel =
    typeof props.previousSupport === "number"
      ? `prev S ${props.previousSupport.toLocaleString("en-IN")}`
      : null;
  const previousResistanceLabel =
    typeof props.previousResistance === "number"
      ? `prev R ${props.previousResistance.toLocaleString("en-IN")}`
      : null;
  const breakoutUpDisplay = fallbackPercent(props.breakoutProbabilityUp, trackSummary?.positionPercent ?? 50);
  const breakoutDownDisplay = fallbackPercent(props.breakoutProbabilityDown, 100 - (trackSummary?.positionPercent ?? 50));
  const trapDisplay =
    typeof props.trapProbability === "number" && Number.isFinite(props.trapProbability)
      ? Math.max(0, Math.min(100, props.trapProbability))
      : 0;
  const readinessDisplay =
    typeof props.readinessScore === "number" && Number.isFinite(props.readinessScore)
      ? Math.max(0, Math.min(100, props.readinessScore))
      : 0;

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
            <div className="spc-hero-row">
              <div className="spc-hero-copy">
                <div className="spc-hero-state">{structuralStateLabel}</div>
                <div className="spc-hero-phase">{phaseLabel}</div>
              </div>
              {props.bias ? (
                <div className="spc-hero-bias">
                  {props.bias}
                  {props.biasStrength ? ` · ${props.biasStrength}` : ""}
                </div>
              ) : null}
            </div>
            <div className="spc-compact-head">
              <div className="spc-compact-metric">
                <span>Support</span>
                <strong>S {trackSummary.supportLabel}</strong>
                {typeof props.supportDefenseRatio === "number" ? (
                  <em className="spc-compact-defense">
                    <span className={`spc-defense-dot ${props.supportDefenseRatio >= 1.0 ? "spc-defense-dot-green" : "spc-defense-dot-red"}`} />
                    PE/CE {props.supportDefenseRatio.toFixed(2)}x
                  </em>
                ) : null}
                {previousSupportLabel ? <em className="spc-compact-prev">{previousSupportLabel}</em> : null}
              </div>
              <div className="spc-compact-metric spc-compact-metric-spot">
                <span>Spot</span>
                <strong>{trackSummary.spot.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong>
                <em className="spc-compact-center-meta">{trackSummary.positionText}</em>
              </div>
              <div className="spc-compact-metric">
                <span>Resistance</span>
                <strong>R {trackSummary.resistanceLabel}</strong>
                {typeof props.resistanceDefenseRatio === "number" ? (
                  <em className="spc-compact-defense">
                    <span className={`spc-defense-dot ${props.resistanceDefenseRatio >= 1.0 ? "spc-defense-dot-green" : "spc-defense-dot-red"}`} />
                    CE/PE {props.resistanceDefenseRatio.toFixed(2)}x
                  </em>
                ) : null}
                {previousResistanceLabel ? <em className="spc-compact-prev">{previousResistanceLabel}</em> : null}
              </div>
            </div>
            <div className="spc-range-meta">
              <span className="spc-range-label">Defended Structure</span>
              <span className="spc-range-label">Active Band</span>
              <span className={`spc-range-label ${watchZone?.tone === "resistance" ? "spc-range-label-watch" : watchZone?.tone === "support" ? "spc-range-label-watch-support" : ""}`}>
                {trackSummary.isUpperThird ? "Breakout Watch" : trackSummary.isLowerThird ? "Breakdown Watch" : "Watch Zone"}
              </span>
            </div>
            <div className="spc-range-submeta">
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
              {watchZone ? (
                <div
                  className={`spc-watch-zone ${watchZone.tone === "resistance" ? "spc-watch-zone-resistance" : "spc-watch-zone-support"}`}
                  style={{ left: watchZone.left, width: watchZone.width }}
                />
              ) : null}
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
                className={`spc-range-spot ${
                  trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance
                    ? "spc-range-spot-breach"
                    : trackSummary.nearSupport
                      ? "spc-range-spot-near-s"
                      : trackSummary.nearResistance
                        ? "spc-range-spot-near-r"
                        : ""
                }`}
                style={{ left: `${trackSummary.spotPct}%` }}
              />
            </div>
            {breachBanner ? (
              <div className={breachBanner.className}>
                <span className="spc-breach-dot" />
                <span>{breachBanner.text}</span>
              </div>
            ) : null}
            <div className="spc-range-foot spc-range-foot-legacy">
              <span className={trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                {trackSummary.footCenterText}
              </span>
              <span className="spc-range-foot-core">
                Up {formatCompactNumber(props.breakoutProbabilityUp, 0)}% · Trap {formatCompactNumber(props.trapProbability, 0)}% · Readiness {formatCompactNumber(props.readinessScore, 0)}
              </span>
              <span className={trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                {trackSummary.footRightText} · Break +50
              </span>
            </div>
            <div className="spc-range-foot spc-range-foot-dense">
              <div className="spc-foot-col spc-foot-col-left">
                <span className={trackSummary.hasBrokenSupport || trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                  {trackSummary.footCenterText}
                </span>
                <span>
                  Trap: {props.trapDirection === "upside" ? "Support absorption" : props.trapDirection === "downside" ? "Resistance rejection" : "No active trap"} {formatCompactNumber(trapDisplay, 0)}%
                </span>
              </div>
              <div className="spc-foot-col spc-foot-col-center spc-foot-col-center-legacy">
                <span className="spc-range-foot-core">
                  Up Prob {formatCompactNumber(props.breakoutProbabilityUp, 0)}% · Down Prob {formatCompactNumber(props.breakoutProbabilityDown, 0)}%
                </span>
                <span>
                  Readiness {formatCompactNumber(props.readinessScore, 0)} · Bias {props.bias || "-"}
                </span>
              </div>
              <div className="spc-foot-col spc-foot-col-right">
                <span className={trackSummary.hasBrokenResistance ? "spc-range-foot-alert" : undefined}>
                  {trackSummary.footRightText}
                </span>
                <span>Break conf: +50 pts</span>
              </div>
              <div className="spc-foot-col spc-foot-col-center">
                <span className="spc-range-foot-core">
                  Up Prob {formatCompactNumber(breakoutUpDisplay, 0)}% · Down Prob {formatCompactNumber(breakoutDownDisplay, 0)}%
                </span>
                <span>
                  Readiness {formatCompactNumber(readinessDisplay, 0)} · Bias {props.bias || "-"}
                </span>
              </div>
            </div>
            <div className="spc-range-subfoot">
              <span className="spc-range-foot-range">Expected Range {compactRangeTarget.text}</span>
            </div>
            <div className="spc-mini-grid spc-mini-grid-legacy">
              <div className="spc-mini-card">
                <span>Band</span>
                <strong>{Math.round(trackSummary.baseBandWidth)} pts</strong>
              </div>
              <div className="spc-mini-card">
                <span>Distances</span>
                <strong>{trackSummary.footCenterText}</strong>
                <em>{trackSummary.footRightText}</em>
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
            previousSupport={props.previousSupport ?? null}
            previousResistance={props.previousResistance ?? null}
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
