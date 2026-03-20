type KeyLevelsCardProps = {
  majorSupport?: string;
  majorResistance?: string;
  support: string;
  resistance: string;
  supportDefenseRatio?: number | null;
  resistanceDefenseRatio?: number | null;
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

function defenseCopy(value: number) {
  if (value >= 1.5) {
    return { label: "Strongly defended", className: "ia-defense-strong" };
  }
  if (value < 1.0) {
    return { label: "Exposed", className: "ia-defense-exposed" };
  }
  return { label: "Defended", className: "ia-defense-neutral" };
}

export default function KeyLevelsCard(props: KeyLevelsCardProps) {
  const supportNum = parseNumeric(props.support);
  const resistanceNum = parseNumeric(props.resistance);
  const majorSupportNum = parseNumeric(props.majorSupport ?? "");
  const majorResistanceNum = parseNumeric(props.majorResistance ?? "");
  const breakoutTriggerNum = parseNumeric(props.breakoutTrigger ?? "");

  const showMajorSupport =
    majorSupportNum !== null && supportNum !== null && majorSupportNum < supportNum;
  const showBreakoutTrigger =
    breakoutTriggerNum !== null && resistanceNum !== null && breakoutTriggerNum > resistanceNum;
  const showMajorResistance =
    majorResistanceNum !== null &&
    resistanceNum !== null &&
    majorResistanceNum > resistanceNum &&
    (supportNum === null || majorResistanceNum > supportNum);
  const supportDefenseMeta =
    typeof props.supportDefenseRatio === "number" ? defenseCopy(props.supportDefenseRatio) : null;
  const resistanceDefenseMeta =
    typeof props.resistanceDefenseRatio === "number" ? defenseCopy(props.resistanceDefenseRatio) : null;

  return (
    <div className="ia-card ia-key-levels-card">
      <h3 className="ia-card-title">Key Levels</h3>
      <div className="ia-key-levels-stack">
        <div className="ia-levels-top-grid">
          <div className="ia-key-level-block">
            <div className="ia-kpi-label">Support</div>
            <div className="ia-level-support ia-emphasis-high">{props.support}</div>
            {supportDefenseMeta ? (
              <div className={`ia-key-defense-copy ${supportDefenseMeta.className}`}>
                {supportDefenseMeta.label} ({props.supportDefenseRatio?.toFixed(2)}x)
              </div>
            ) : null}
            {showMajorSupport ? (
              <div className="ia-kpi-label ia-key-major-label">Next Support: {props.majorSupport}</div>
            ) : null}
          </div>
          <div className="ia-key-level-block">
            <div className="ia-kpi-label">Resistance</div>
            <div className="ia-level-resistance ia-emphasis-high">{props.resistance}</div>
            {resistanceDefenseMeta ? (
              <div className={`ia-key-defense-copy ${resistanceDefenseMeta.className}`}>
                {resistanceDefenseMeta.label} ({props.resistanceDefenseRatio?.toFixed(2)}x)
              </div>
            ) : null}
            {showBreakoutTrigger ? (
              <div className="ia-kpi-label ia-key-major-label">Confirm Above: {props.breakoutTrigger}</div>
            ) : null}
            {showMajorResistance ? (
              <div className="ia-kpi-label ia-key-major-label">Next Resistance: {props.majorResistance}</div>
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
