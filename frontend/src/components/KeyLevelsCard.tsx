type KeyLevelsCardProps = {
  support: string;
  resistance: string;
  target1: string;
  target2: string;
  supportRange?: string;
  resistanceRange?: string;
  supportPressure?: string;
  resistancePressure?: string;
};

export default function KeyLevelsCard(props: KeyLevelsCardProps) {
  return (
    <div className="ia-card">
      <h3 className="ia-card-title">Key Levels</h3>
      <div className="ia-levels-grid">
        <div>
          <div className="ia-kpi-label">Support</div>
          <div className="ia-level-support ia-emphasis-high">{props.support}</div>
          {(props.supportRange || props.supportPressure) ? (
            <div className="ia-kpi-label">
              {props.supportRange ? `${props.supportRange}` : ""}
              {props.supportRange && props.supportPressure ? " | " : ""}
              {props.supportPressure ? `Pressure: ${props.supportPressure}` : ""}
            </div>
          ) : null}
        </div>
        <div>
          <div className="ia-kpi-label">Resistance</div>
          <div className="ia-level-resistance ia-emphasis-high">{props.resistance}</div>
          {(props.resistanceRange || props.resistancePressure) ? (
            <div className="ia-kpi-label">
              {props.resistanceRange ? `${props.resistanceRange}` : ""}
              {props.resistanceRange && props.resistancePressure ? " | " : ""}
              {props.resistancePressure ? `Pressure: ${props.resistancePressure}` : ""}
            </div>
          ) : null}
        </div>
        <div>
          <div className="ia-kpi-label">Target 1</div>
          <div className="ia-kpi-value ia-emphasis-medium">{props.target1}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Target 2</div>
          <div className="ia-kpi-value ia-emphasis-medium">{props.target2}</div>
        </div>
      </div>
    </div>
  );
}
