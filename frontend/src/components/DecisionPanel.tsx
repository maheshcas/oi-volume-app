import MarketStructureScoreBadge from "./MarketStructureScoreBadge";
import { useState } from "react";
import MarketPressureBar from "./MarketPressureBar";
import TradeReadinessIndicator from "./TradeReadinessIndicator";

type DecisionPanelProps = {
  bias: "Bullish" | "Bearish" | "Neutral";
  regime?: string;
  bullProbability: number;
  bearProbability: number;
  confidence: number;
  trapRisk: number;
  reversalRisk: number;
  summaryLine: string;
  alignmentCount: number;
  marketingMode?: boolean;
  adaptiveMode?: string;
  adaptiveOiWeight?: number;
  adaptiveBreakoutWeight?: number;
  marketStructureScore?: number;
  structureState?: string;
  structureBadge?: string;
  pressureBadge?: string;
  trapBadge?: string;
  projection?: string;
  conflictState?: string;
  pressureScore?: number;
  pressureStateLabel?: string;
  readinessState?: "WAIT" | "CAUTION" | "READY";
  readinessScore?: number;
};

export default function DecisionPanel(props: DecisionPanelProps) {
  const [showMetrics, setShowMetrics] = useState(false);
  const marketingMode = !!props.marketingMode;
  const confidenceStrength =
    props.confidence >= 70 ? "Strong" : props.confidence >= 50 ? "Moderate" : "Weak";
  const veryLowConfidence = props.confidence < 35;
  const lowConfidence = marketingMode ? confidenceStrength === "Weak" : props.confidence < 40;
  const clampedAlignment = Math.max(0, Math.min(4, props.alignmentCount));
  const structuralAgreementRatio = clampedAlignment / 4;
  const isRangeRegime = String(props.regime || "").toLowerCase().includes("range");
  const spread = Math.abs(Number(props.bullProbability || 0) - Number(props.bearProbability || 0));
  const structuralAgreementLabel = clampedAlignment >= 4 ? "Strong" : clampedAlignment === 3 ? "Moderate" : "Weak";
  const enginesConflict = structuralAgreementLabel === "Weak";
  const probabilityConflict = spread < 20; // equivalent to <60/40 split
  const conflictDetected = probabilityConflict || enginesConflict;
  const decisionMode = conflictDetected
    ? "Conflict Detected"
    : props.confidence >= 70 && structuralAgreementLabel === "Strong"
      ? "High Conviction Trend"
      : props.confidence >= 50
        ? "Moderate Bias"
        : props.confidence < 50 && isRangeRegime
          ? "Low Clarity Range"
          : "Moderate Bias";
  const modeClass =
    decisionMode === "Conflict Detected"
      ? "ia-decision-conflict"
      : decisionMode === "High Conviction Trend"
        ? "ia-decision-high"
        : decisionMode === "Moderate Bias"
          ? "ia-decision-moderate"
          : "ia-decision-low-clarity";
  const lowClarityBias =
    props.bias !== "Neutral" &&
    structuralAgreementRatio < 0.5 &&
    props.confidence < 50 &&
    isRangeRegime;
  const alignmentLabel = structuralAgreementLabel;
  const tone =
    props.bias === "Bullish"
      ? "ia-bias-bull"
      : props.bias === "Bearish"
        ? "ia-bias-bear"
        : "ia-bias-neutral";
  const biasLabel =
    conflictDetected
      ? "Conflict Detected — Standby"
      : props.bias === "Neutral"
        ? `Neutral — ${decisionMode}`
      : lowClarityBias
        ? `${props.bias} — Low Clarity Range`
      : lowConfidence
        ? `${props.bias} — ${decisionMode}`
        : `${props.bias} — ${decisionMode}`;

  return (
    <div className={`ia-card ia-decision-hero ${modeClass}`}>
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Decision Layer</h3>
        <MarketStructureScoreBadge
          score={props.marketStructureScore}
          state={props.structureState}
        />
      </div>
      <div className="ia-bias-wrap">
        {conflictDetected ? <span className="ia-conflict-icon">⚠</span> : null}
        <span
          className={`ia-bias-pill ia-bias-pill-hero ${tone} ${lowConfidence ? "ia-bias-weak" : ""} ${
            veryLowConfidence ? "ia-bias-neutral-weak" : ""
          } ia-emphasis-high`}
        >
          {biasLabel}
        </span>
        {veryLowConfidence ? (
          <div className="ia-kpi-label" style={{ marginTop: 6 }}>
            Low directional conviction
          </div>
        ) : null}
      </div>
      <TradeReadinessIndicator
        state={props.readinessState ?? "WAIT"}
        score={props.readinessScore ?? 0}
      />
      <div className="ia-kpi-label ia-decision-summary">
        {props.summaryLine.length > 80
          ? `${props.summaryLine.slice(0, 77)}...`
          : props.summaryLine}
      </div>
      <div className="ia-status-badges">
        <span className="ia-status-chip">
          State: {props.structureBadge ?? props.structureState ?? "-"} | Pressure: {props.pressureBadge ?? "-"}
        </span>
        <span className="ia-status-chip ia-emphasis-medium">Projection: {props.projection ?? "No Confirmed Breakout"}</span>
        {!conflictDetected ? <span className="ia-status-chip">Conflict: {props.conflictState ?? "Balanced"}</span> : null}
      </div>
      <MarketPressureBar
        score={props.pressureScore ?? 0}
        state={props.pressureStateLabel ?? "Balanced"}
      />
      {!marketingMode ? (
        <button type="button" className="ia-detail-toggle" style={{ marginTop: 10 }} onClick={() => setShowMetrics((v) => !v)}>
          {showMetrics ? "Hide Metrics" : "Show Metrics"}
        </button>
      ) : null}
      {!marketingMode && showMetrics ? (
        <>
          <div className="ia-confidence-wrap ia-emphasis-low">
            <div className="ia-kpi-label" title="Structural alignment strength across engines.">
              Confidence
            </div>
            <div className="ia-kpi-value ia-confidence-value">{props.confidence}%</div>
            <div className="ia-confidence-track">
              <div className="ia-confidence-fill" style={{ width: `${props.confidence}%` }} />
            </div>
          </div>
          {(props.readinessState ?? "WAIT") !== "WAIT" ? (
            <>
              <div className="ia-prob-track">
                <div className="ia-prob-bull" style={{ width: `${props.bullProbability}%` }} />
                <div className="ia-prob-bear" style={{ width: `${props.bearProbability}%` }} />
              </div>
              <div className="ia-prob-legend ia-emphasis-low" title="Directional bias weight distribution.">
                <span>Bull {props.bullProbability}%</span>
                <span>Bear {props.bearProbability}%</span>
              </div>
            </>
          ) : null}
          <div className="ia-kpi-grid">
            <div>
              <div className="ia-kpi-label">Reversal Risk</div>
              <div className="ia-mini-track">
                <div className="ia-mini-fill ia-mini-fill-reversal" style={{ width: `${props.reversalRisk}%` }} />
              </div>
              <div className="ia-kpi-value ia-kpi-value-sm">{props.reversalRisk}%</div>
            </div>
            <div className="ia-emphasis-low">
              <div className="ia-kpi-label">Structural Agreement</div>
              <div className="ia-kpi-value">{alignmentLabel}</div>
            </div>
          </div>
          <div className="ia-kpi-label ia-emphasis-low" style={{ marginTop: 8 }}>
            Adaptive Mode: {props.adaptiveMode ?? "Base"} | OI Weight:{" "}
            {props.adaptiveOiWeight !== undefined ? `${Math.round(props.adaptiveOiWeight * 100)}%` : "-"} | Breakout
            Weight:{" "}
            {props.adaptiveBreakoutWeight !== undefined ? `${Math.round(props.adaptiveBreakoutWeight * 100)}%` : "-"}
          </div>
        </>
      ) : null}
    </div>
  );
}
