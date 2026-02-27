type BreakoutCheck = {
  label: string;
  confirmed: boolean;
};

type StructuralDiagnosticsProps = {
  open: boolean;
  onToggle: () => void;
  atmCeOi: string;
  atmPeOi: string;
  atmCeVol: string;
  atmPeVol: string;
  institutionalLevels: string;
  expectedMove: string;
  shift: string;
  checklist: BreakoutCheck[];
};

export default function StructuralDiagnostics(props: StructuralDiagnosticsProps) {
  return (
    <div className="ia-card">
      <button
        type="button"
        onClick={props.onToggle}
        className="ia-struct-toggle"
      >
        <span className="ia-card-title">
          Structural Diagnostics
        </span>
        <span className="ia-kpi-label">{props.open ? "Hide" : "Show"}</span>
      </button>
      {props.open ? (
        <div className="ia-struct-grid">
          <div>
            <div className="ia-kpi-label">ATM CE OI / Vol</div>
            <div>{props.atmCeOi} / {props.atmCeVol}</div>
          </div>
          <div>
            <div className="ia-kpi-label">ATM PE OI / Vol</div>
            <div>{props.atmPeOi} / {props.atmPeVol}</div>
          </div>
          <div>
            <div className="ia-kpi-label">Institutional Levels</div>
            <div>{props.institutionalLevels}</div>
          </div>
          <div>
            <div className="ia-kpi-label">Expected Move</div>
            <div>{props.expectedMove}</div>
          </div>
          <div className="ia-col-span-2">
            <div className="ia-kpi-label">Shift</div>
            <div>{props.shift}</div>
          </div>
          <div className="ia-col-span-2">
            <div className="ia-kpi-label ia-mb-1">Breakout Checklist</div>
            <ul className="ia-check-list">
              {props.checklist.map((item) => (
                <li key={item.label} className="ia-check-item">
                  <span className={`ia-check-status ${item.confirmed ? "ia-level-support" : "ia-level-resistance"}`}>
                    {item.confirmed ? "✓" : "✕"}
                  </span>
                  <span className="ia-check-label">{item.label}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}
