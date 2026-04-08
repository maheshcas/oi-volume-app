import { useMemo } from "react";
import StructureBand from "./StructureBand";

type Props = {
  spotPrice: number | null;
  dayOpen?: number | null;
  dayHigh?: number | null;
  dayLow?: number | null;
  supportLevel?: number | null;
  resistanceLevel?: number | null;
  majorSupport?: number | null;
  majorResistance?: number | null;
  supportDefenseRatio?: number | null;
  resistanceDefenseRatio?: number | null;
  supportStart: number | null;
  supportEnd: number | null;
  resistanceStart: number | null;
  resistanceEnd: number | null;
  target1: number | null;
  target2: number | null;
  breakBelowPrimary?: string | null;
  breakAbovePrimary?: string | null;
  previousSupport?: number | null;
  previousResistance?: number | null;
  materialBreachConfirmed?: boolean;
  confirmationType?: string | null;
  sessionPhase?: string | null;
  tradeAction?: string | null;
  resolvedReason?: string | null;
  decisionExplanation?: string | null;
  decisionConfidence?: number | null;
  readinessState?: string | null;
  readinessExplainability?: string | null;
  supportTransitionActive?: boolean;
  supportTransitionBadge?: boolean;
  resistanceTransitionBadge?: boolean;
  bias: string;
  biasStrength: string;
  regime: string;
  breakoutProbabilityUp?: number | null;
  breakoutProbabilityDown?: number | null;
  trapProbability?: number | null;
  trapDirection?: "upside" | "downside" | "";
  readinessScore?: number | null;
  trapZoneLabel?: string;
  volumeLabel?: string;
};

const fmt = (v: number | null | undefined, d = 0) =>
  typeof v === "number" && Number.isFinite(v)
    ? v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d })
    : "-";
const phaseLabel = (v?: string | null) => {
  const t = String(v || "").trim();
  if (!t) return "Transition Phase";
  return t.toLowerCase().includes("phase") ? t : `${t} Phase`;
};
const actionLabel = (v?: string | null) => String(v || "").trim() || "WAIT";
const human = (v: string | null | undefined, fb: string) => {
  const t = String(v || "").trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
  return t ? `${t.charAt(0).toUpperCase()}${t.slice(1)}` : fb;
};
const confidenceLabel = (v?: number | null) => (typeof v === "number" && Number.isFinite(v) ? (v >= 75 ? "High" : v >= 55 ? "Moderate" : "Low") : null);
const trapBadge = (v?: number | null) => {
  const risk = typeof v === "number" && Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : 0;
  if (risk <= 10) return "No Trap";
  if (risk >= 60) return `High Trap ${Math.round(risk)}%`;
  return `Trap Risk ${Math.round(risk)}%`;
};
type SPCLabelState =
  | "BELOW_SUPPORT"
  | "ABOVE_RESISTANCE"
  | "NEAR_SUPPORT"
  | "NEAR_RESISTANCE"
  | "LOWER_BAND"
  | "UPPER_BAND"
  | "MID_BAND";

const resolveSPCLabelState = ({
  position,
  distToSupport,
  distToResistance,
}: {
  position: number;
  distToSupport: number;
  distToResistance: number;
}): SPCLabelState => {
  if (distToSupport < 0) return "BELOW_SUPPORT";
  if (distToResistance < 0) return "ABOVE_RESISTANCE";
  if (distToSupport <= 25) return "NEAR_SUPPORT";
  if (distToResistance <= 25) return "NEAR_RESISTANCE";
  if (position <= 33) return "LOWER_BAND";
  if (position >= 67) return "UPPER_BAND";
  return "MID_BAND";
};

const positionSummary = ({
  position,
  distToSupport,
  distToResistance,
}: {
  position: number;
  distToSupport: number;
  distToResistance: number;
}) => {
  const labelState = resolveSPCLabelState({ position, distToSupport, distToResistance });
  switch (labelState) {
    case "BELOW_SUPPORT":
      return `Below support (${Math.round(Math.abs(distToSupport))} pts below)`;
    case "ABOVE_RESISTANCE":
      return `Above resistance (${Math.round(Math.abs(distToResistance))} pts above)`;
    case "NEAR_SUPPORT":
      return `Near support (${Math.round(distToSupport)} pts above)`;
    case "NEAR_RESISTANCE":
      return `Near resistance (${Math.round(distToResistance)} pts below)`;
    case "LOWER_BAND":
      return "Close to support";
    case "UPPER_BAND":
      return "Close to resistance";
    default:
      return "Inside active band";
  }
};

const sanitizeReadinessExplainability = (value?: string | null) => {
  const text = String(value || "").trim();
  if (!text) return null;
  if (text.toLowerCase() === "no clean edge") return null;
  return text;
};
const probabilityLabel = (v?: number | null) => {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  const pct = Math.max(0, Math.min(100, v));
  const tone = pct >= 60 ? "High" : pct >= 35 ? "Moderate" : "Low";
  return `${Math.round(pct)}% (${tone})`;
};
const formatPhaseBadge = ({
  phase,
  supportTransition,
  resistanceTransition,
}: {
  phase?: string | null;
  supportTransition: boolean;
  resistanceTransition: boolean;
}) => {
  if (supportTransition) return "Support Transition";
  if (resistanceTransition) return "Resistance Transition";
  const base = phaseLabel(phase);
  if (String(phase || "").toLowerCase().includes("transition")) return "Transition Phase";
  return base;
};
const buildAlertMessage = ({
  summary,
}: {
  summary: {
    brokenS: boolean;
    brokenR: boolean;
    nearS: boolean;
    nearR: boolean;
    support: number;
    resistance: number;
    posRaw: number;
    distS: number;
    distR: number;
  };
}) => {
  const labelState = resolveSPCLabelState({
    position: summary.posRaw,
    distToSupport: summary.distS,
    distToResistance: summary.distR,
  });
  if (labelState === "BELOW_SUPPORT") return `Below support - watching for continuation under ${fmt(summary.support)}`;
  if (labelState === "ABOVE_RESISTANCE") return `Above resistance - watching for acceptance over ${fmt(summary.resistance)}`;
  if (labelState === "NEAR_SUPPORT") return `Approaching support at ${fmt(summary.support)}`;
  if (labelState === "NEAR_RESISTANCE") return `Approaching resistance at ${fmt(summary.resistance)}`;
  return null;
};
const readinessGlowOpacity = (score?: number | null, state?: string | null) => {
  if (typeof score === "number" && Number.isFinite(score)) {
    return Math.max(0.14, Math.min(0.68, score / 100));
  }
  const normalized = String(state || "").toLowerCase();
  if (normalized === "high") return 0.68;
  if (normalized === "moderate") return 0.5;
  if (normalized === "low") return 0.28;
  return 0.16;
};
const formatReason = ({
  resolvedReason,
  decisionExplanation,
  action,
  phase,
  supportTransition,
  resistanceTransition,
  trapRisk,
  bias,
}: {
  resolvedReason?: string | null;
  decisionExplanation?: string | null;
  action: string;
  phase?: string | null;
  supportTransition: boolean;
  resistanceTransition: boolean;
  trapRisk: number;
  bias: string;
}) => {
  const resolved = human(resolvedReason, "");
  if (resolved && resolved.toLowerCase() !== "no clear signal") return resolved;
  const explanation = human(decisionExplanation, "");
  if (explanation && explanation.toLowerCase() !== "no clear signal") return explanation;
  if (supportTransition || resistanceTransition) return "Transition phase - waiting for structural clarity";
  if (trapRisk >= 60) return "Trap risk elevated - waiting for clean confirmation";
  if (action.toUpperCase().includes("BREAKOUT")) return "Resistance pressure building - waiting for upside acceptance";
  if (action.toUpperCase().includes("BREAKDOWN")) return "Support under pressure - watching for continuation";
  if (String(phase || "").toLowerCase().includes("transition")) return "Price inside range - no breakout confirmation";
  if (String(bias || "").toLowerCase() === "bullish") return "Support holding but no clean confirmation yet";
  if (String(bias || "").toLowerCase() === "bearish") return "Resistance holding but no clean confirmation yet";
  return "Inside active band - no clean directional edge";
};

const formatStructuralHeadline = ({
  summary,
  fallbackReason,
}: {
  summary: {
    support: number;
    resistance: number;
    posRaw: number;
    distS: number;
    distR: number;
  };
  fallbackReason: string;
}) => {
  const labelState = resolveSPCLabelState({
    position: summary.posRaw,
    distToSupport: summary.distS,
    distToResistance: summary.distR,
  });
  if (labelState === "ABOVE_RESISTANCE") {
    return `Above resistance - waiting for acceptance over ${fmt(summary.resistance)}`;
  }
  if (labelState === "BELOW_SUPPORT") {
    return `Below support - watching for continuation under ${fmt(summary.support)}`;
  }
  return fallbackReason;
};
const actionTone = (v: string) => {
  const t = v.toUpperCase();
  if (t.includes("BREAKOUT") || t.includes("LONG")) return "bullish";
  if (t.includes("BREAKDOWN") || t.includes("SHORT")) return "bearish";
  if (t.includes("ABSORPTION")) return "amber";
  return "neutral";
};
const biasTone = (value?: string | null) => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized.includes("bearish")) return "bearish";
  if (normalized.includes("bullish")) return "bullish";
  return "neutral";
};

export default function StructuralPriceContextCard(props: Props) {



  const summary = useMemo(() => {
    if (props.spotPrice == null || props.supportLevel == null || props.resistanceLevel == null) return null;
    let support = props.supportLevel;
    let resistance = props.resistanceLevel;

    if (resistance <= support) {
      const fallbackMajorResistance =
        typeof props.majorResistance === "number" && Number.isFinite(props.majorResistance) && props.majorResistance > support
          ? props.majorResistance
          : null;
      const fallbackMajorSupport =
        typeof props.majorSupport === "number" && Number.isFinite(props.majorSupport) && props.majorSupport < resistance
          ? props.majorSupport
          : null;

      if (fallbackMajorResistance != null) {
        resistance = fallbackMajorResistance;
      } else if (fallbackMajorSupport != null) {
        support = fallbackMajorSupport;
      } else {
        return null;
      }
    }

    const prevS = typeof props.previousSupport === "number" && props.previousSupport !== support ? props.previousSupport : null;
    const prevR = typeof props.previousResistance === "number" && props.previousResistance !== resistance ? props.previousResistance : null;
    const band = resistance - support;
    const posRaw = ((props.spotPrice - support) / band) * 100;
    const distS = props.spotPrice - support;
    const distR = resistance - props.spotPrice;
    const brokenS = props.spotPrice < support;
    const brokenR = props.spotPrice > resistance;
    const nearS = distS >= 0 && distS < 30 && !brokenS && !brokenR;
    const nearR = distR >= 0 && distR < 30 && !brokenS && !brokenR;
    return {
      support, resistance, prevS, prevR, band, spot: props.spotPrice, distS, distR, posRaw, brokenS, brokenR, nearS, nearR,
      supportShifted: prevS != null,
      resistanceShifted: prevR != null,
      upperThird: posRaw >= 67, lowerThird: posRaw <= 33,
    };
  }, [
    props.majorResistance,
    props.majorSupport,
    props.previousResistance,
    props.previousSupport,
    props.resistanceLevel,
    props.spotPrice,
    props.supportLevel,
  ]);

  const breachBanner = useMemo(() => {
    if (!summary) return null;
    const labelState = resolveSPCLabelState({
      position: summary.posRaw,
      distToSupport: summary.distS,
      distToResistance: summary.distR,
    });
    if (labelState === "BELOW_SUPPORT") {
      return { className: "spc-breach-banner spc-breach-banner-support-break", text: buildAlertMessage({ summary }) };
    }
    if (labelState === "ABOVE_RESISTANCE") {
      return { className: "spc-breach-banner spc-breach-banner-resistance-break", text: buildAlertMessage({ summary }) };
    }
    if (labelState === "NEAR_SUPPORT") {
      return { className: "spc-breach-banner spc-breach-banner-near-s", text: buildAlertMessage({ summary }) };
    }
    if (labelState === "NEAR_RESISTANCE") {
      return { className: "spc-breach-banner spc-breach-banner-near-r", text: buildAlertMessage({ summary }) };
    }
    return null;
  }, [summary]);

  const rangeText = useMemo(() => {
    const targets = [props.target1, props.target2].filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
    if (!targets.length) return "Range -";
    return `${fmt(Math.min(...targets))} to ${fmt(Math.max(...targets))}`;
  }, [props.target1, props.target2]);

  if (!summary) {
    return (
      <div className="spc-card">
        <div className="spc-head">
          <div><div className="spc-title">Structural Price Context</div></div>
        </div>
        <div className="spc-compact-panel"><div className="spc-compact-empty">Support, resistance, or spot is not available yet.</div></div>
      </div>
    );
  }

  const trapRisk = typeof props.trapProbability === "number" && Number.isFinite(props.trapProbability) ? Math.max(0, Math.min(100, props.trapProbability)) : 0;
  const readiness = typeof props.readinessScore === "number" && Number.isFinite(props.readinessScore) ? Math.max(0, Math.min(100, props.readinessScore)) : null;
  const act = actionLabel(props.tradeAction);
  const supportTransition = Boolean(props.supportTransitionBadge ?? props.supportTransitionActive);
  const resistanceTransition = Boolean(props.resistanceTransitionBadge);
  const baseReason = formatReason({
    resolvedReason: props.resolvedReason,
    decisionExplanation: props.decisionExplanation,
    action: act,
    phase: props.sessionPhase,
    supportTransition,
    resistanceTransition,
    trapRisk,
    bias: props.bias,
  });
  const reason = formatStructuralHeadline({
    summary,
    fallbackReason: baseReason,
  });
  const confLabel = confidenceLabel(props.decisionConfidence);
  const phaseBadge = formatPhaseBadge({
    phase: props.sessionPhase,
    supportTransition,
    resistanceTransition,
  });
  const readinessGlow = readinessGlowOpacity(readiness, props.readinessState);
  const readinessExplainability = sanitizeReadinessExplainability(props.readinessExplainability);
  const positionTextFriendly = positionSummary({
    position: summary.posRaw,
    distToSupport: summary.distS,
    distToResistance: summary.distR,
  });
  const watchZoneLabel = "Resistance Watch";
  const watchZoneToneClass =
    summary.upperThird || summary.nearR
      ? "spc-range-label-watch"
      : summary.lowerThird || summary.nearS
        ? "spc-range-label-watch-support"
        : "";

  return (
    <div className="spc-card">
      <div className="spc-head">
        <div>
          <div className="spc-title">Structural Price Context</div>
        </div>
      </div>
      <div className="spc-compact-panel">
        <div className="spc-hero-row">
          <div className="spc-hero-copy spc-hero-copy-decision">
            <div className={`spc-action-label spc-action-${actionTone(act)}`}>{act}</div>
            <div className="spc-hero-state">{reason}</div>
          </div>
          <div className="spc-hero-side">
            <div className="spc-hero-side-row">
              <div className={`spc-hero-bias spc-hero-bias-${biasTone(props.bias)}`}>Bias: {props.bias}</div>
              {typeof props.decisionConfidence === "number" && confLabel ? <div className={`spc-confidence-chip spc-confidence-${confLabel.toLowerCase()}`}>Confidence: {confLabel} {Math.round(props.decisionConfidence)}%</div> : null}
            </div>
          </div>
        </div>
        <div className="spc-status-row spc-status-row-decision">
          <span className="spc-chip spc-chip-neutral">{phaseBadge}</span>
          <span className={`spc-chip ${trapRisk >= 60 ? "spc-chip-danger" : trapRisk >= 25 ? "spc-chip-warning" : "spc-chip-success"}`}>
            {trapRisk <= 10 ? "No Trap - clean structure" : trapBadge(props.trapProbability)}
          </span>
        </div>
        <div className="spc-compact-head">
          <div className="spc-compact-metric spc-compact-metric-support">
            <span>Support</span>
            <div className="spc-compact-value-row">
              <strong className="spc-compact-token">S</strong>
              <strong className="spc-compact-level">{fmt(summary.support)}</strong>
              {summary.supportShifted ? <span className="spc-compact-state-badge">NEW</span> : null}
            </div>
            {typeof props.supportDefenseRatio === "number" ? <em className="spc-compact-defense"><span className={`spc-defense-dot ${props.supportDefenseRatio >= 1 ? "spc-defense-dot-green" : "spc-defense-dot-red"}`} />PE/CE {props.supportDefenseRatio.toFixed(2)}x</em> : null}
            {summary.prevS != null ? <em className="spc-compact-prev">prev S {fmt(summary.prevS)}</em> : null}
          </div>
          <div className="spc-compact-metric spc-compact-metric-spot">
            <span>Spot</span>
            <strong>{fmt(summary.spot, 2)}</strong>
            <em className="spc-compact-center-meta">{positionTextFriendly}</em>
          </div>
          <div className="spc-compact-metric spc-compact-metric-resistance">
            <span>Resistance</span>
            <div className="spc-compact-value-row">
              <strong className="spc-compact-token">R</strong>
              <strong className="spc-compact-level">{fmt(summary.resistance)}</strong>
              {summary.resistanceShifted ? <span className="spc-compact-state-badge">NEW</span> : null}
            </div>
            {typeof props.resistanceDefenseRatio === "number" ? <em className="spc-compact-defense"><span className={`spc-defense-dot ${props.resistanceDefenseRatio >= 1 ? "spc-defense-dot-green" : "spc-defense-dot-red"}`} />CE/PE {props.resistanceDefenseRatio.toFixed(2)}x</em> : null}
            {summary.prevR != null ? <em className="spc-compact-prev">prev R {fmt(summary.prevR)}</em> : null}
          </div>
        </div>
        <div className="spc-range-meta">
          <span className="spc-range-label">Defended Support</span>
          <span className="spc-range-label">Active Zone</span>
          <span className={`spc-range-label ${watchZoneToneClass}`}>{watchZoneLabel}</span>
        </div>
        <div className="spc-band-stack">
          <StructureBand
            spot={summary.spot}
            support={summary.support}
            resistance={summary.resistance}
            previousSupport={summary.prevS ?? undefined}
            previousResistance={summary.prevR ?? undefined}
            supportBroken={summary.brokenS}
            resistanceBroken={summary.brokenR}
            isNearSupport={summary.nearS}
            isNearResistance={summary.nearR}
            materialBreachConfirmed={props.materialBreachConfirmed}
            confirmationType={props.confirmationType}
            trapProbability={props.trapProbability ?? undefined}
            trapDirection={props.trapDirection}
            trapAffectedLevel={
              props.trapDirection === "downside"
                ? summary.resistance
                : props.trapDirection === "upside"
                  ? summary.support
                  : undefined
            }
            embedded
            className="spc-embedded-band"
          />
          <div className="spc-readiness-rail-glow-wrap" aria-hidden="true">
            <div className="spc-readiness-rail-glow" style={{ opacity: readinessGlow }} />
          </div>
        </div>
        {breachBanner ? <div className={breachBanner.className}><span className="spc-breach-dot" /><span>{breachBanner.text}</span></div> : null}
        <div className="spc-range-foot spc-range-foot-dense">
          <div className="spc-foot-col spc-foot-col-left">
            <span />
          </div>
          <div className="spc-foot-col spc-foot-col-center" />
          <div className="spc-foot-col spc-foot-col-right">
            <span>Breakout needs +50 pts</span>
          </div>
        </div>
        <div className="spc-range-subfoot">
          <div className="spc-range-subfoot-side spc-range-subfoot-side-left">
            {probabilityLabel(props.breakoutProbabilityDown) ? (
              <span className="spc-range-subfoot-prob">Down Prob {probabilityLabel(props.breakoutProbabilityDown)}</span>
            ) : null}
            {props.breakBelowPrimary && props.breakBelowPrimary !== "-" ? (
              <span>Below S target {props.breakBelowPrimary}</span>
            ) : null}
          </div>
          <div className="spc-range-subfoot-center">
            <span className="spc-range-foot-range-label">Today's Expected Range</span>
            <span className="spc-range-foot-range">{rangeText}</span>
          </div>
          <div className="spc-range-subfoot-side spc-range-subfoot-side-right">
            {probabilityLabel(props.breakoutProbabilityUp) ? (
              <span className="spc-range-subfoot-prob">Up Prob {probabilityLabel(props.breakoutProbabilityUp)}</span>
            ) : null}
            {props.breakAbovePrimary && props.breakAbovePrimary !== "-" ? (
              <span>Above R target {props.breakAbovePrimary}</span>
            ) : null}
          </div>
        </div>
        {readinessExplainability ? (
          <div className="spc-readiness-explain">{readinessExplainability}</div>
        ) : null}
      </div>
    </div>
  );
}
