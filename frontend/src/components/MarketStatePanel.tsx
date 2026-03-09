type MarketStatePanelProps = {
  state: string;
  bias: "Bullish" | "Bearish" | "Neutral";
  microBias: "Bullish" | "Bearish" | "Neutral";
  frameworkStatus: string;
  drift: string;
  retailMapping: {
    force: string;
    clarity: string;
    risk: string;
  };
  directionalForce: {
    bull: number;
    bear: number;
    strength: number;
  };
  clarity: number;
  executionRisk: number;
  summaryLine: string;
  engineContributions: {
    oi: number;
    volume: number;
    breakout: number;
    writer: number;
  };
};

function meterClass(kind: "force" | "clarity" | "risk", value: number) {
  if (kind === "force") {
    if (value > 60) return "ia-meter-good";
    if (value >= 40) return "ia-meter-warn";
    return "ia-meter-neutral";
  }
  if (kind === "clarity") {
    if (value > 65) return "ia-meter-good";
    if (value >= 45) return "ia-meter-warn";
    return "ia-meter-bad";
  }
  if (value < 30) return "ia-meter-good";
  if (value <= 60) return "ia-meter-warn";
  return "ia-meter-bad";
}

export default function MarketStatePanel(props: MarketStatePanelProps) {
  const force = Math.max(0, Math.min(100, props.directionalForce.strength));
  const bullForce = Math.max(0, Math.min(100, props.directionalForce.bull));
  const bearForce = Math.max(0, Math.min(100, props.directionalForce.bear));
  const isBearDominant = bearForce > bullForce;
  const isBullDominant = bullForce > bearForce;
  const dominantForce = Math.max(bullForce, bearForce);
  const clarity = Math.max(0, Math.min(100, props.clarity));
  const risk = Math.max(0, Math.min(100, props.executionRisk));

  return (
    <div className="ia-card ia-market-state">
      <h3 className="ia-card-title">Market State</h3>
      <div className="ia-state-label">{props.state || `${props.bias} Bias`}</div>
      <div className="ia-state-meta">
        <span>Primary Bias: {props.bias}</span>
        <span>Micro Bias: {props.microBias}</span>
        <span>Framework: {props.frameworkStatus}</span>
        <span>Drift: {props.drift}</span>
      </div>
      <div className="ia-kpi-label ia-state-summary">{props.summaryLine}</div>

      <div className="ia-meters">
        <div className="ia-meter-row">
          <span>Directional Force</span>
          <span>
            {force}%{props.retailMapping.force ? ` (${props.retailMapping.force})` : ""}
          </span>
          <div className="ia-meter-track">
            <div
              className={`ia-meter-fill ${
                isBearDominant ? "ia-meter-bear" : isBullDominant ? "ia-meter-bull" : meterClass("force", force)
              } ${isBearDominant ? "ia-meter-fill-right" : ""}`}
              style={{ width: `${dominantForce}%` }}
            />
          </div>
          <div className="ia-force-label">
            {isBearDominant ? "Bearish Bias" : isBullDominant ? "Bullish Bias" : "Neutral Bias"}
          </div>
        </div>
        <div className="ia-meter-row">
          <span>Structural Clarity</span>
          <span>
            {clarity.toFixed(0)}%{props.retailMapping.clarity ? ` (${props.retailMapping.clarity})` : ""}
          </span>
          <div className="ia-meter-track">
            <div
              className={`ia-meter-fill ${meterClass("clarity", clarity)} ${
                clarity < 45 ? "ia-meter-clarity-fragile" : ""
              }`}
              style={{ width: `${clarity}%` }}
            />
          </div>
        </div>
        <div className="ia-meter-row">
          <span>Execution Risk</span>
          <span>
            {risk.toFixed(0)}%{props.retailMapping.risk ? ` (${props.retailMapping.risk})` : ""}
          </span>
          <div className="ia-meter-track">
            <div className={`ia-meter-fill ${meterClass("risk", risk)}`} style={{ width: `${risk}%` }} />
          </div>
        </div>
      </div>

      <details className="ia-struct-details">
        <summary>Structural Diagnostics</summary>
        <div className="ia-struct-grid">
          <div>OI - {props.engineContributions.oi >= 0 ? "+" : ""}{props.engineContributions.oi.toFixed(3)}</div>
          <div>Volume - {props.engineContributions.volume >= 0 ? "+" : ""}{props.engineContributions.volume.toFixed(3)}</div>
          <div>Breakout - {props.engineContributions.breakout >= 0 ? "+" : ""}{props.engineContributions.breakout.toFixed(3)}</div>
          <div>Writer - {props.engineContributions.writer >= 0 ? "+" : ""}{props.engineContributions.writer.toFixed(3)}</div>
        </div>
      </details>
    </div>
  );
}
