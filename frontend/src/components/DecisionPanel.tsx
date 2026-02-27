type DecisionPanelProps = {
  bias: "Bullish" | "Bearish" | "Neutral";
  bullProbability: number;
  bearProbability: number;
  confidence: number;
  trapRisk: number;
  reversalRisk: number;
  volatilityState?: "Expanding" | "Contracting" | "Stable";
};

export default function DecisionPanel(props: DecisionPanelProps) {
  const tone =
    props.bias === "Bullish"
      ? "ia-bias-bull"
      : props.bias === "Bearish"
        ? "ia-bias-bear"
        : "ia-bias-neutral";

  return (
    <div className="ia-card">
      <h3 className="ia-card-title">Decision Layer</h3>
      {props.volatilityState ? (
        <div className={`ia-vol-chip ia-vol-${props.volatilityState.toLowerCase()}`}>
          Volatility: {props.volatilityState}
        </div>
      ) : null}
      <div className="ia-bias-wrap">
        <span className={`ia-bias-pill ${tone}`}>{props.bias}</span>
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
          <div className="ia-kpi-label">Confidence</div>
          <div className="ia-kpi-value">{props.confidence}%</div>
        </div>
        <div>
          <div className="ia-kpi-label">Trap Risk</div>
          <div className="ia-kpi-value">{props.trapRisk}%</div>
        </div>
        <div>
          <div className="ia-kpi-label">Reversal Risk</div>
          <div className="ia-kpi-value">{props.reversalRisk}%</div>
        </div>
      </div>
    </div>
  );
}
