import { useMemo } from "react";
import StructureBand from "./StructureBand";
import StructureBandBar from "./StructureBandBar";

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
  blockingReason?: string | null;
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
  spcState?: string | null;
  moveQuality?: string | null;
  spcDecision?: string | null;
  readinessScore?: number | null;
  trapZoneLabel?: string;
  volumeLabel?: string;
  entryZone?: string | null;
  stopZone?: string | null;
  targetZone?: string | null;
  executionMode?: string | null;
  deltaGuidance?: string | null;
  bullishTrigger?: string | null;
  bearishTrigger?: string | null;
  invalidation?: string | null;
  peWall?: number | null;
  ceWall?: number | null;
  magnet?: number | null;
  maxPain?: number | null;
  strikeGap?: number | null;
  strikes?: Array<{
    strike: number;
    oi_ce: number;
    oi_pe: number;
    tag?: "pe_wall" | "ce_wall" | "magnet" | "maxpain" | null;
  }> | null;
  chainGreeks?: Array<{
    strike: number;
    ce?: { delta?: number; ltp?: number };
    pe?: { delta?: number; ltp?: number };
  }> | null;
};

const fmt = (v: number | null | undefined, d = 0) =>
  typeof v === "number" && Number.isFinite(v)
    ? v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d })
    : "-";

const phaseLabel = (v?: string | null) => {
  const t = String(v || "").trim();
  if (!t) return "Transition";
  return t.toLowerCase().includes("phase") ? t : `${t} Phase`;
};
const actionLabel = (v?: string | null) => String(v || "").trim() || "WAIT";
const human = (v: string | null | undefined, fb: string) => {
  const t = String(v || "").trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
  return t ? `${t.charAt(0).toUpperCase()}${t.slice(1)}` : fb;
};
const trapBadge = (v?: number | null) => {
  const risk = typeof v === "number" && Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : 0;
  if (risk <= 10) return "No Trap";
  if (risk >= 60) return `High Trap ${Math.round(risk)}%`;
  return `Trap ${Math.round(risk)}%`;
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
      return `${Math.round(Math.abs(distToSupport))} pts below S`;
    case "ABOVE_RESISTANCE":
      return `+${Math.round(Math.abs(distToResistance))} pts above R`;
    case "NEAR_SUPPORT":
      return `${Math.round(distToSupport)} pts above S`;
    case "NEAR_RESISTANCE":
      return `${Math.round(distToResistance)} pts below R`;
    case "LOWER_BAND":
      return "Close to support";
    case "UPPER_BAND":
      return "Close to resistance";
    default:
      return "Inside band";
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
  const tone = pct >= 60 ? "High" : pct >= 35 ? "Mid" : "Low";
  return `${Math.round(pct)}% ${tone}`;
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
  if (String(phase || "").toLowerCase().includes("transition")) return "Transition";
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
  if (labelState === "BELOW_SUPPORT")
    return `Below support · ${fmt(summary.support)} — watch for failed reclaim or breakdown continuation`;
  if (labelState === "ABOVE_RESISTANCE")
    return `Above resistance · ${fmt(summary.resistance)} — watch for acceptance or false breakout reversal`;
  if (labelState === "NEAR_SUPPORT")
    return `Approaching support · ${fmt(summary.support)} — watch for absorption or rejection`;
  if (labelState === "NEAR_RESISTANCE")
    return `Approaching resistance · ${fmt(summary.resistance)} — watch for rejection or breakout attempt`;
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
  blockingReason,
  phase,
  supportTransition,
  resistanceTransition,
  trapRisk,
  bias,
}: {
  resolvedReason?: string | null;
  decisionExplanation?: string | null;
  action: string;
  blockingReason?: string | null;
  phase?: string | null;
  supportTransition: boolean;
  resistanceTransition: boolean;
  trapRisk: number;
  bias: string;
}) => {
  const blocker = String(blockingReason || "").trim().toUpperCase();
  if (blocker && blocker !== "NONE") {
    if (blocker === "TRAP_HIGH") return "Fake breakout risk";
    if (blocker === "NO_BREAK_CONFIRMATION" || blocker === "NO_BREACH_CONFIRMATION")
      return "No breakout confirmation";
    if (blocker === "ABSORPTION_ACTIVE") return "Support absorption active";
    if (blocker === "SUPPORT_TRANSITION") return "Support transition active";
    if (blocker === "RESISTANCE_TRANSITION") return "Resistance transition active";
    if (blocker === "RANGE_CONFLICT") return "Range conflict";
    if (blocker === "LOW_READINESS") return "Readiness below threshold";
  }
  const resolved = human(resolvedReason, "");
  if (resolved && resolved.toLowerCase() !== "no clear signal") return resolved;
  const explanation = human(decisionExplanation, "");
  if (explanation && explanation.toLowerCase() !== "no clear signal") return explanation;
  if (supportTransition || resistanceTransition) return "Transition phase — waiting for structural clarity";
  if (trapRisk >= 60) return "Trap risk elevated — waiting for clean confirmation";
  if (action.toUpperCase().includes("BREAKOUT")) return "Resistance pressure building — waiting for upside acceptance";
  if (action.toUpperCase().includes("BREAKDOWN")) return "Support under pressure — watching for continuation";
  if (String(phase || "").toLowerCase().includes("transition")) return "Price inside range — no breakout confirmation";
  if (String(bias || "").toLowerCase() === "bullish") return "Support holding — no clean confirmation yet";
  if (String(bias || "").toLowerCase() === "bearish") return "Resistance holding — no clean confirmation yet";
  return "Inside active band — no directional edge";
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
  if (labelState === "ABOVE_RESISTANCE")
    return `Above resistance · waiting for acceptance over ${fmt(summary.resistance)}`;
  if (labelState === "BELOW_SUPPORT")
    return `Below support · watching for continuation under ${fmt(summary.support)}`;
  return fallbackReason;
};

const compactTagLabel = (value?: string | null, fallback = "-") => {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  const normalized = raw.toUpperCase();
  if (normalized === "SUSPECT") return "LOW QUALITY";
  return raw.replace(/_/g, " ").replace(/\s+/g, " ").trim();
};

const compactTagTone = (kind: "state" | "quality" | "decision", value?: string | null) => {
  const t = String(value || "").trim().toUpperCase();
  if (kind === "quality") {
    if (t === "TRUSTED") return "ok";
    if (t === "FAKE") return "bad";
    return "warn";
  }
  if (kind === "decision") {
    if (t === "ACT") return "ok";
    if (t === "DISTRUST") return "bad";
    return "warn";
  }
  if (t.includes("CONFIRMED")) return "ok";
  if (t.includes("ATTEMPT") || t.includes("PRESSURE") || t.includes("DEFENSE")) return "warn";
  return "neutral";
};

export default function StructuralPriceContextCard(props: Props) {
  const summary = useMemo(() => {
    if (props.spotPrice == null || props.supportLevel == null || props.resistanceLevel == null)
      return null;
    let support = props.supportLevel;
    let resistance = props.resistanceLevel;
    const originalResistance = resistance;

    if (resistance <= support) {
      const fallbackMajorResistance =
        typeof props.majorResistance === "number" &&
        Number.isFinite(props.majorResistance) &&
        props.majorResistance > support
          ? props.majorResistance
          : null;
      const fallbackMajorSupport =
        typeof props.majorSupport === "number" &&
        Number.isFinite(props.majorSupport) &&
        props.majorSupport < resistance
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

    const effectiveResistance =
      props.spotPrice > resistance &&
      typeof props.ceWall === "number" &&
      Number.isFinite(props.ceWall) &&
      props.ceWall > resistance
        ? props.ceWall
        : resistance;
    resistance = effectiveResistance;

    const prevS =
      typeof props.previousSupport === "number" && props.previousSupport !== support
        ? props.previousSupport
        : null;
    const prevR =
      typeof props.previousResistance === "number" && props.previousResistance !== resistance
        ? props.previousResistance
        : null;
    const band = resistance - support;
    const posRaw = ((props.spotPrice - support) / band) * 100;
    const distS = props.spotPrice - support;
    const distR = resistance - props.spotPrice;
    const brokenS = props.spotPrice < support;
    const brokenR = props.spotPrice > resistance;
    const nearS = distS >= 0 && distS < 30 && !brokenS && !brokenR;
    const nearR = distR >= 0 && distR < 30 && !brokenS && !brokenR;
    return {
      support,
      resistance,
      originalResistance,
      prevS,
      prevR,
      band,
      spot: props.spotPrice,
      distS,
      distR,
      posRaw,
      brokenS,
      brokenR,
      nearS,
      nearR,
      supportShifted: prevS != null,
      resistanceShifted: prevR != null,
      upperThird: posRaw >= 67,
      lowerThird: posRaw <= 33,
    };
  }, [
    props.majorResistance,
    props.majorSupport,
    props.ceWall,
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
    if (labelState === "BELOW_SUPPORT")
      return { className: "spc-breach-banner spc-breach-banner-support-break", text: buildAlertMessage({ summary }) };
    if (labelState === "ABOVE_RESISTANCE")
      return { className: "spc-breach-banner spc-breach-banner-resistance-break", text: buildAlertMessage({ summary }) };
    if (labelState === "NEAR_SUPPORT")
      return { className: "spc-breach-banner spc-breach-banner-near-s", text: buildAlertMessage({ summary }) };
    if (labelState === "NEAR_RESISTANCE")
      return { className: "spc-breach-banner spc-breach-banner-near-r", text: buildAlertMessage({ summary }) };
    return null;
  }, [summary]);

  const rangeText = useMemo(() => {
    const targets = [props.target1, props.target2].filter(
      (v): v is number => typeof v === "number" && !Number.isNaN(v),
    );
    if (!targets.length) return null;
    return `${fmt(Math.min(...targets))} – ${fmt(Math.max(...targets))}`;
  }, [props.target1, props.target2]);

  if (!summary) {
    return (
      <div className="spc-card">
        <div className="spc-head">
          <div className="spc-title">Structure</div>
        </div>
        <div className="spc-compact-panel">
          <div className="spc-compact-empty">Support, resistance, or spot is not available yet.</div>
        </div>
      </div>
    );
  }

  const trapRisk =
    typeof props.trapProbability === "number" && Number.isFinite(props.trapProbability)
      ? Math.max(0, Math.min(100, props.trapProbability))
      : 0;
  const readiness =
    typeof props.readinessScore === "number" && Number.isFinite(props.readinessScore)
      ? Math.max(0, Math.min(100, props.readinessScore))
      : null;
  const act = actionLabel(props.tradeAction);
  const supportTransition = Boolean(props.supportTransitionBadge ?? props.supportTransitionActive);
  const resistanceTransition = Boolean(props.resistanceTransitionBadge);

  const baseReason = formatReason({
    resolvedReason: props.resolvedReason,
    decisionExplanation: props.decisionExplanation,
    action: act,
    blockingReason: props.blockingReason,
    phase: props.sessionPhase,
    supportTransition,
    resistanceTransition,
    trapRisk,
    bias: props.bias,
  });
  const reason = formatStructuralHeadline({ summary, fallbackReason: baseReason });
  const blockingReasonCode = String(props.blockingReason || "").trim().toUpperCase();
  const dominantMessage =
    blockingReasonCode && blockingReasonCode !== "NONE"
      ? `${baseReason} · Decision Engine`
      : reason;

  const phaseBadge = formatPhaseBadge({ phase: props.sessionPhase, supportTransition, resistanceTransition });
  const readinessGlow = readinessGlowOpacity(readiness, props.readinessState);
  const readinessExplainability = sanitizeReadinessExplainability(props.readinessExplainability);

  const distToS =
    Number.isFinite(summary.spot) && Number.isFinite(summary.support)
      ? Math.round(summary.spot - summary.support)
      : null;
  const distToR =
    Number.isFinite(summary.spot) && Number.isFinite(summary.resistance)
      ? Math.round(summary.resistance - summary.spot)
      : null;

  const proximitySummary = positionSummary({
    position: summary.posRaw,
    distToSupport: summary.distS,
    distToResistance: summary.distR,
  });

  /* ── Determine proximity tone for center spot display ── */
  const spotToneClass = summary.brokenR
    ? "spc-spot-tone-above"
    : summary.brokenS
      ? "spc-spot-tone-below"
      : distToR !== null && distToR < 50
        ? "spc-spot-tone-near-r"
        : distToS !== null && distToS < 50
          ? "spc-spot-tone-near-s"
          : "";

  return (
    <div className="spc-card">
      {/* ═══════════════════════════════════════════
          HEADER — title + all status chips in one row
      ═══════════════════════════════════════════ */}
      <div className="spc-header-row">
        <span className="spc-title">Structure</span>
        <div className="spc-header-chips">
          <span className="spc-chip spc-chip-neutral">{phaseBadge}</span>
          <span
            className={`spc-chip ${
              trapRisk >= 60
                ? "spc-chip-danger"
                : trapRisk >= 25
                  ? "spc-chip-warning"
                  : "spc-chip-success"
            }`}
          >
            {trapRisk <= 10 ? "Clean" : trapBadge(props.trapProbability)}
          </span>
          {(props.spcState || props.moveQuality) ? (
            <span
              className={`spc-chip spc-chip-compact spc-chip-compact-${compactTagTone("state", props.spcState)}`}
            >
              {compactTagLabel(props.spcState)}
              {props.moveQuality ? ` · ${compactTagLabel(props.moveQuality)}` : ""}
            </span>
          ) : null}
        </div>
      </div>

      {/* ═══════════════════════════════════════════
          HEADLINE — single dominant structural message
      ═══════════════════════════════════════════ */}
      <div className="spc-headline">{dominantMessage}</div>

      {/* ═══════════════════════════════════════════
          LEVELS HERO — Support | Spot | Resistance
          (defense ratios + distances — shown once)
      ═══════════════════════════════════════════ */}
      <div className="spc-levels-hero">
        {/* Support */}
        <div className="spc-level-col spc-level-col-support">
          <span className="spc-level-label">SUPPORT</span>
          <div className="spc-level-value-row">
            <span className="spc-level-token spc-level-token-s">S</span>
            <span className="spc-level-price spc-level-price-s">{fmt(summary.support)}</span>
          </div>
          {typeof props.supportDefenseRatio === "number" ? (
            <span className="spc-level-defense">
              <span
                className={`spc-defense-dot ${
                  props.supportDefenseRatio >= 1 ? "spc-defense-dot-green" : "spc-defense-dot-red"
                }`}
              />
              PE/CE {props.supportDefenseRatio.toFixed(2)}x
              <em className="spc-defense-status">
                {props.supportDefenseRatio >= 1 ? "Defended" : "Exposed"}
              </em>
            </span>
          ) : null}
          {distToS !== null ? (
            <span className="spc-level-dist spc-level-dist-s">
              {summary.brokenS ? `−${Math.abs(distToS)} pts` : `+${distToS} pts`}
            </span>
          ) : null}
        </div>

        {/* Spot (center) */}
        <div className="spc-level-col spc-level-col-spot">
          <span className="spc-level-label">SPOT</span>
          <span className={`spc-spot-price ${spotToneClass}`}>
            {summary.spot.toLocaleString("en-IN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
          <span className="spc-spot-proximity">{proximitySummary}</span>
        </div>

        {/* Resistance */}
        <div className="spc-level-col spc-level-col-resistance">
          <span className="spc-level-label">RESISTANCE</span>
          <div className="spc-level-value-row spc-level-value-row-right">
            <span className="spc-level-token spc-level-token-r">R</span>
            <span className="spc-level-price spc-level-price-r">{fmt(summary.resistance)}</span>
          </div>
          {summary.originalResistance !== summary.resistance ? (
            <span className="spc-level-defense spc-level-defense-right">
              CE Wall active ceiling
            </span>
          ) : null}
          {typeof props.resistanceDefenseRatio === "number" ? (
            <span className="spc-level-defense spc-level-defense-right">
              CE/PE {props.resistanceDefenseRatio.toFixed(2)}x
              <em className="spc-defense-status">
                {props.resistanceDefenseRatio >= 1 ? "Defended" : "Exposed"}
              </em>
              <span
                className={`spc-defense-dot ${
                  props.resistanceDefenseRatio >= 1 ? "spc-defense-dot-green" : "spc-defense-dot-red"
                }`}
              />
            </span>
          ) : null}
          {distToR !== null ? (
            <span className="spc-level-dist spc-level-dist-r">
              {summary.brokenR ? `+${Math.abs(distToR)} pts` : `−${distToR} pts`}
            </span>
          ) : null}
        </div>
      </div>

      {/* ═══════════════════════════════════════════
          VISUAL BAND (StructureBand SVG track)
      ═══════════════════════════════════════════ */}
      <div className="spc-band-block">
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

      {/* ═══════════════════════════════════════════
          OI BAR — embedded mode (no duplicate stats/zones)
      ═══════════════════════════════════════════ */}
      <StructureBandBar
        spot={summary.spot}
        support={summary.support}
        resistance={summary.resistance}
        previousResistance={summary.prevR}
        peWall={props.peWall}
        ceWall={props.ceWall}
        magnet={props.magnet}
        maxPain={props.maxPain}
        strikeGap={typeof props.strikeGap === "number" ? props.strikeGap : 50}
        strikes={props.strikes ?? undefined}
        chainGreeks={props.chainGreeks ?? undefined}
        embedded
      />

      {/* ═══════════════════════════════════════════
          READINESS EXPLAINABILITY
      ═══════════════════════════════════════════ */}
      {readinessExplainability ? (
        <div className="spc-readiness-explain">{readinessExplainability}</div>
      ) : null}

      {/* ═══════════════════════════════════════════
          BREACH / PROXIMITY ALERT BANNER
      ═══════════════════════════════════════════ */}
      {breachBanner ? (
        <div className={breachBanner.className}>
          <span className="spc-breach-dot" />
          <span>{breachBanner.text}</span>
        </div>
      ) : null}

      {/* ═══════════════════════════════════════════
          FOOTER — probabilities + expected range
      ═══════════════════════════════════════════ */}
      <div className="spc-footer-row">
        <div className="spc-footer-prob spc-footer-prob-down">
          {probabilityLabel(props.breakoutProbabilityDown) ? (
            <>
              <span className="spc-footer-prob-lbl">↓ Down</span>
              <span className="spc-footer-prob-val">{probabilityLabel(props.breakoutProbabilityDown)}</span>
            </>
          ) : null}
          {props.breakBelowPrimary && props.breakBelowPrimary !== "-" ? (
            <span className="spc-footer-target">T↓ {props.breakBelowPrimary}</span>
          ) : null}
        </div>

        {rangeText ? (
          <div className="spc-footer-range">
            <span className="spc-footer-range-lbl">Expected Range</span>
            <span className="spc-footer-range-val">{rangeText}</span>
          </div>
        ) : null}

        <div className="spc-footer-prob spc-footer-prob-up">
          {probabilityLabel(props.breakoutProbabilityUp) ? (
            <>
              <span className="spc-footer-prob-lbl">↑ Up</span>
              <span className="spc-footer-prob-val">{probabilityLabel(props.breakoutProbabilityUp)}</span>
            </>
          ) : null}
          {props.breakAbovePrimary && props.breakAbovePrimary !== "-" ? (
            <span className="spc-footer-target">T↑ {props.breakAbovePrimary}</span>
          ) : null}
        </div>
      </div>

      {/* ═══════════════════════════════════════════
          TRIGGER STRIP
      ═══════════════════════════════════════════ */}
      {(props.bullishTrigger || props.bearishTrigger || props.invalidation) ? (
        <div className="spc-trigger-strip">
          {props.bullishTrigger ? (
            <div className="spc-trigger-row">
              <span className="spc-trigger-label spc-trigger-label-bull">▲ Bullish trigger</span>
              <span className="spc-trigger-value">{props.bullishTrigger}</span>
            </div>
          ) : null}
          {props.bearishTrigger ? (
            <div className="spc-trigger-row">
              <span className="spc-trigger-label spc-trigger-label-bear">▼ Bearish trigger</span>
              <span className="spc-trigger-value">{props.bearishTrigger}</span>
            </div>
          ) : null}
          {props.invalidation ? (
            <div className="spc-trigger-row">
              <span className="spc-trigger-label">✕ Invalidation</span>
              <span className="spc-trigger-value">{props.invalidation}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
