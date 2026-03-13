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
  directionalPressureLabel?: string;
  readinessState?: string;
  readinessScore?: number;
  institutionalStructure?: {
    put_wall?: number | null;
    call_wall?: number | null;
  };
  marketInsight?: string[];
  absorptionDetected?: boolean;
  absorptionLevel?: number | null;
};

export default function DecisionPanel(props: DecisionPanelProps) {
  const tone =
    props.bias === "Bullish"
      ? "ia-bias-bull"
      : props.bias === "Bearish"
        ? "ia-bias-bear"
        : "ia-bias-neutral";

  const summary = props.summaryLine?.trim() || 'Waiting for clearer movement between active boundaries.';
  const absorptionNote = props.absorptionDetected && props.absorptionLevel ? ` - absorption active at ${Number(props.absorptionLevel).toLocaleString('en-IN')}` : '';
  const summaryWithAbsorption = `${summary}${absorptionNote}`;
  const shortSummary = summaryWithAbsorption.length > 120 ? `${summaryWithAbsorption.slice(0, 117)}...` : summaryWithAbsorption;
  const insightLine = props.marketInsight?.find((item) => item && item.trim().length > 0) ?? 'No fresh structural insight.';
  const pressureText = String(props.pressureStateLabel ?? 'Balanced').replace(/\s*Pressure$/i, '').trim() || 'Balanced';
  const wallParts = [
    props.institutionalStructure?.put_wall ? `Put Wall ${Number(props.institutionalStructure.put_wall).toLocaleString('en-IN')}` : null,
    props.institutionalStructure?.call_wall ? `Call Wall ${Number(props.institutionalStructure.call_wall).toLocaleString('en-IN')}` : null,
  ].filter(Boolean);

  return (
    <div className="ia-card ia-decision-hero">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Decision Layer</h3>
      </div>

      <div className="ia-decision-header-grid">
        <div className="ia-decision-header-main">
          <div className="ia-kpi-label ia-decision-side-label">Structure Bias</div>
          <div className="ia-bias-wrap">
            <span className={`ia-bias-pill ia-bias-pill-hero ${tone} ia-emphasis-high`}>
              {props.bias === 'Neutral' ? 'Neutral Bias' : props.bias}
            </span>
          </div>
        </div>

        <div className="ia-decision-header-side">
          <div className="ia-kpi-label ia-decision-side-label">Trade Action</div>
          <TradeReadinessIndicator state={props.readinessState ?? 'WAIT'} score={props.readinessScore ?? 0} />
          {props.directionalPressureLabel ? (
            <div className="ia-decision-pressure-chip-wrap">
              <span className="ia-status-chip ia-decision-pressure-chip">
                Pressure: {props.directionalPressureLabel.replace(/\s*Pressure$/i, '')}
              </span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="ia-decision-range">
        <div className="ia-kpi-label ia-decision-side-label">Key Range</div>
        <div className="ia-kpi-label ia-decision-summary">{shortSummary}</div>
      </div>

      <div className="ia-market-insight-strip ia-decision-section">
        <div className="ia-market-insight-title">Market Insight</div>
        {wallParts.length ? <div className="ia-market-insight-inline">{wallParts.join(' | ')}</div> : null}
        <div className="ia-market-insight-inline">{insightLine}</div>
      </div>

      <div className="ia-decision-section">
        <div className="ia-kpi-label ia-decision-side-label">Immediate Pressure</div>
        <MarketPressureBar score={props.pressureScore ?? 0} state={pressureText} />
      </div>
    </div>
  );
}
