type KeyLevelsCardProps = {
  support: string;
  resistance: string;
  target1: string;
  target2: string;
};

export default function KeyLevelsCard(props: KeyLevelsCardProps) {
  return (
    <div className="ia-card">
      <h3 className="ia-card-title">Key Levels</h3>
      <div className="ia-levels-grid">
        <div>
          <div className="ia-kpi-label">Support</div>
          <div className="ia-level-support">{props.support}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Resistance</div>
          <div className="ia-level-resistance">{props.resistance}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Target 1</div>
          <div className="ia-kpi-value">{props.target1}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Target 2</div>
          <div className="ia-kpi-value">{props.target2}</div>
        </div>
      </div>
    </div>
  );
}
