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
  institutionalStructure?: {
    put_wall?: number | null;
    call_wall?: number | null;
  };
  marketInsight?: string[];
};

export default function DecisionPanel(props: DecisionPanelProps) {
  const [showMetrics, setShowMetrics] = useState(false);
  const marketingMode = !!props.marketingMode;
  const veryLowConfidence = props.confidence < 35;
  const lowConfidence = marketingMode ? props.confidence < 50 : props.confidence < 40;
  const clampedAlignment = Math.max(0, Math.min(4, props.alignmentCount));
  const structuralAgreementLabel = clampedAlignment >= 4 ? "Strong" : clampedAlignment === 3 ? "Moderate" : "Weak";
  const structuralAgreementRatio = clampedAlignment / 4;
  const isRangeRegime = String(props.regime || "").toLowerCase().includes("range");
  const lowClarityBias =
    props.bias !== "Neutral" && structuralAgreementRatio < 0.5 && props.confidence < 50 && isRangeRegime;

  const tone =
    props.bias === "Bullish"
      ? "ia-bias-bull"
      : props.bias === "Bearish"
        ? "ia-bias-bear"
        : "ia-bias-neutral";
  const biasBaseLabel = props.bias === "Neutral" ? "Neutral Bias" : props.bias;
  const biasLabel = lowClarityBias ? `${biasBaseLabel} - Low Clarity` : biasBaseLabel;
  const rawStructureState = String(props.structureBadge ?? props.structureState ?? "").trim();
  const structureLabel =
    !rawStructureState || rawStructureState === "-"
      ? "Balanced"
      : /^high trap risk$/i.test(rawStructureState)
        ? "Boundary Trap Risk"
        : rawStructureState;
  const rawPressureLabel = String(props.pressureBadge ?? props.pressureStateLabel ?? "").trim();
  const pressureLabel = rawPressureLabel || "Balanced";
  const rawConflictState = String(props.conflictState ?? "").trim();
  const conflictLabel =
    !rawConflictState || /^balanced$/i.test(rawConflictState)
      ? "Balanced"
      : /^conflict$/i.test(rawConflictState)
        ? "Mixed Structure"
        : /^high trap risk$/i.test(rawConflictState)
          ? "Range Conflict"
          : rawConflictState;
  const trapLabel =
    props.trapRisk >= 60
      ? pressureLabel.toLowerCase().includes("stable") || pressureLabel.toLowerCase().includes("balanced")
        ? "High false-breakout risk near support/resistance."
        : "High trap risk while pressure is still unstable."
      : props.trapRisk >= 40
        ? "Moderate trap risk near active boundaries."
        : "Trap risk remains controlled.";
  const structureContext =
    props.marketStructureScore === undefined || props.marketStructureScore === null
      ? "Structure context unavailable"
      : props.marketStructureScore < 35
        ? "Structure is fragile"
        : props.marketStructureScore < 60
          ? "Structure is developing"
          : "Structure is aligned";

  return (
    <div className="ia-card ia-decision-hero">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Decision Layer</h3>
        <MarketStructureScoreBadge score={props.marketStructureScore} state={props.structureState} />
      </div>

      <div className="ia-kpi-label" style={{ marginTop: -4 }}>
        {structureContext}
      </div>

      <div className="ia-bias-wrap">
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

      <TradeReadinessIndicator state={props.readinessState ?? "WAIT"} score={props.readinessScore ?? 0} />

      <div className="ia-kpi-label ia-decision-summary">
        {props.summaryLine.length > 80 ? `${props.summaryLine.slice(0, 77)}...` : props.summaryLine}
      </div>

      <div className="ia-status-badges">
        <span className="ia-status-chip">
          State: {structureLabel} | Pressure: {pressureLabel}
        </span>
        <span className="ia-status-chip ia-emphasis-medium">Projection: {props.projection ?? "No Confirmed Breakout"}</span>
        <span className="ia-status-chip">Structure: {conflictLabel}</span>
      </div>

      <div className="ia-kpi-label ia-decision-summary" style={{ marginTop: 0 }}>
        {trapLabel}
      </div>

      <MarketPressureBar score={props.pressureScore ?? 0} state={pressureLabel} />

      {(props.marketInsight?.length || props.institutionalStructure?.put_wall || props.institutionalStructure?.call_wall) ? (
        <div className="ia-market-insight-strip">
          <div className="ia-market-insight-title">Market Insight</div>
          <div className="ia-market-insight-badges">
            {props.institutionalStructure?.put_wall ? (
              <span className="ia-market-insight-chip">Put Wall: {Number(props.institutionalStructure.put_wall).toLocaleString("en-IN")}</span>
            ) : null}
            {props.institutionalStructure?.call_wall ? (
              <span className="ia-market-insight-chip">Call Wall: {Number(props.institutionalStructure.call_wall).toLocaleString("en-IN")}</span>
            ) : null}
          </div>
          {props.marketInsight?.length ? (
            <ul className="ia-market-insight-list">
              {props.marketInsight.slice(0, 3).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

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
              <div className="ia-kpi-value">{structuralAgreementLabel}</div>
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
