type DecisionPanelProps = {
  bias: "Bullish" | "Bearish" | "Neutral";
  bullProbability: number;
  bearProbability: number;
  confidence: number;
  reversalRisk: number;
  summaryLine: string;
  alignmentCount: number;
  adaptiveMode?: string;
  adaptiveOiWeight?: number;
  adaptiveBreakoutWeight?: number;
};

export default function DecisionPanel(props: DecisionPanelProps) {
  const veryLowConfidence = props.confidence < 35;
  const lowConfidence = props.confidence < 40;
  const clampedAlignment = Math.max(0, Math.min(4, props.alignmentCount));
  const alignmentLabel = clampedAlignment >= 4 ? "Strong" : clampedAlignment === 3 ? "Moderate" : "Weak";
  const tone =
    props.bias === "Bullish"
      ? "ia-bias-bull"
      : props.bias === "Bearish"
        ? "ia-bias-bear"
        : "ia-bias-neutral";
  const biasLabel =
    props.bias === "Neutral"
      ? "Neutral"
      : lowConfidence
        ? `${props.bias} (Low Conviction)`
        : props.bias;

  return (
    <div className="ia-card ia-decision-hero">
      <h3 className="ia-card-title">Decision Layer</h3>
      <div className="ia-bias-wrap">
        <span
          className={`ia-bias-pill ia-bias-pill-hero ${tone} ${lowConfidence ? "ia-bias-weak" : ""} ${
            veryLowConfidence ? "ia-bias-neutral-weak" : ""
          }`}
        >
          {biasLabel}
        </span>
        {veryLowConfidence ? (
          <div className="ia-kpi-label" style={{ marginTop: 6 }}>
            Low directional conviction
          </div>
        ) : null}
      </div>
      <div className="ia-kpi-label ia-decision-summary">
        {props.summaryLine}
      </div>
      <div className="ia-confidence-wrap">
        <div className="ia-kpi-label">Confidence</div>
        <div className="ia-kpi-value ia-confidence-value">{props.confidence}%</div>
        <div className="ia-confidence-track">
          <div className="ia-confidence-fill" style={{ width: `${props.confidence}%` }} />
        </div>
      </div>
      <div className="ia-prob-track">
        <div className="ia-prob-bull" style={{ width: `${props.bullProbability}%` }} />
        <div className="ia-prob-bear" style={{ width: `${props.bearProbability}%` }} />
      </div>
      <div className="ia-prob-legend">
        <span>Bull {props.bullProbability}%</span>
        <span>Bear {props.bearProbability}%</span>
      </div>
      <div className="ia-kpi-grid">
        <div>
          <div className="ia-kpi-label">Reversal Risk</div>
          <div className="ia-mini-track">
            <div className="ia-mini-fill ia-mini-fill-reversal" style={{ width: `${props.reversalRisk}%` }} />
          </div>
          <div className="ia-kpi-value ia-kpi-value-sm">{props.reversalRisk}%</div>
        </div>
        <div>
          <div className="ia-kpi-label">Structural Agreement</div>
          <div className="ia-kpi-value">{alignmentLabel}</div>
        </div>
      </div>
      <div className="ia-kpi-label" style={{ marginTop: 8 }}>
        Adaptive Mode: {props.adaptiveMode ?? "Base"} | OI Weight:{" "}
        {props.adaptiveOiWeight !== undefined ? `${Math.round(props.adaptiveOiWeight * 100)}%` : "-"} | Breakout
        Weight: {props.adaptiveBreakoutWeight !== undefined ? `${Math.round(props.adaptiveBreakoutWeight * 100)}%` : "-"}
      </div>
    </div>
  );
}
