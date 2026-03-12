type KeyLevelsCardProps = {
  majorSupport?: string;
  majorResistance?: string;
  support: string;
  resistance: string;
  breakoutTrigger?: string;
  breakAbovePrimary: string;
  breakAboveExtended: string;
  breakBelowPrimary: string;
  breakBelowExtended: string;
  trapRisk: string;
  watchNote: string;
  breakoutProbability?: {
    upside?: number;
    downside?: number;
    upside_state?: string;
    downside_state?: string;
  };
};

function parseNumeric(value: string) {
  const cleaned = String(value ?? '').replace(/,/g, '').trim();
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}

function formatRoundedZone(value: string) {
  const num = parseNumeric(value);
  if (num === null) return value;
  const lower = Math.floor(num / 50) * 50;
  const upper = Math.ceil(num / 50) * 50;
  return `${lower.toLocaleString('en-IN')}-${upper.toLocaleString('en-IN')}`;
}

export default function KeyLevelsCard(props: KeyLevelsCardProps) {
  return (
    <div className="ia-card ia-key-levels-card">
      <h3 className="ia-card-title">Key Levels</h3>
      <div className="ia-key-levels-stack">
        <div className="ia-levels-top-grid">
          <div className="ia-key-level-block">
            <div className="ia-kpi-label">Active Support</div>
            <div className="ia-level-support ia-emphasis-high">{props.support}</div>
            {props.majorSupport && props.majorSupport !== props.support ? (
              <div className="ia-kpi-label ia-key-major-label">Major Support: {props.majorSupport}</div>
            ) : null}
          </div>
          <div className="ia-key-level-block">
            <div className="ia-kpi-label">Active Resistance</div>
            <div className="ia-level-resistance ia-emphasis-high">{props.resistance}</div>
            {props.breakoutTrigger && props.breakoutTrigger !== props.resistance ? (
              <div className="ia-kpi-label ia-key-major-label">Breakout Trigger: {props.breakoutTrigger}</div>
            ) : null}
            {props.majorResistance && props.majorResistance !== props.resistance ? (
              <div className="ia-kpi-label ia-key-major-label">Major Resistance: {props.majorResistance}</div>
            ) : null}
          </div>
        </div>

        <div className="ia-key-breakout-probability">
          <div className="ia-kpi-label">Breakout Probability</div>
          <div className="ia-key-breakout-probability-grid">
            <span className="ia-status-chip">
              Down: {props.breakoutProbability ? `${Math.round(props.breakoutProbability.downside ?? 0)}% (${props.breakoutProbability.downside_state ?? 'Low'})` : '-'}
            </span>
            <span className="ia-status-chip">
              Up: {props.breakoutProbability ? `${Math.round(props.breakoutProbability.upside ?? 0)}% (${props.breakoutProbability.upside_state ?? 'Low'})` : '-'}
            </span>
          </div>
        </div>

        <div className="ia-key-targets">
          <div className="ia-kpi-label">Breakout Targets</div>
        </div>

        <div className="ia-key-target-grid">
          <div className="ia-key-level-block">
            <div className="ia-kpi-label">Below Support</div>
            <div className="ia-kpi-value ia-key-target-primary">{formatRoundedZone(props.breakBelowPrimary)}</div>
            <div className="ia-kpi-label ia-key-target-secondary">Extended: {props.breakBelowExtended}</div>
          </div>
          <div className="ia-key-level-block">
            <div className="ia-kpi-label">Above Resistance</div>
            <div className="ia-kpi-value ia-key-target-primary">{formatRoundedZone(props.breakAbovePrimary)}</div>
            <div className="ia-kpi-label ia-key-target-secondary">Extended: {props.breakAboveExtended}</div>
          </div>
        </div>

        <div className="ia-key-footer-grid ia-key-footer-grid-single">
          <div className="ia-key-note">
            <div className="ia-kpi-label">Watch</div>
            <div className="ia-kpi-value">{props.watchNote}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
