type ExpansionTargetsCardProps = {
  resistance: string;
  support: string;
  breakAbovePrimary: string;
  breakAboveExtended: string;
  breakBelowPrimary: string;
  breakBelowExtended: string;
};

export default function ExpansionTargetsCard({
  resistance,
  support,
  breakAbovePrimary,
  breakAboveExtended,
  breakBelowPrimary,
  breakBelowExtended,
}: ExpansionTargetsCardProps) {
  return (
    <div className="ia-card ia-expansion-card">
      <h3 className="ia-card-title">Expansion Targets</h3>
      <div className="ia-expansion-block ia-expansion-up">
        <div className="ia-kpi-label">Break Above {resistance}</div>
        <div className="ia-kpi-value ia-expansion-zone">{breakAbovePrimary}</div>
        <div className="ia-kpi-label">Target 1</div>
        <div className="ia-kpi-value ia-expansion-zone">{breakAboveExtended}</div>
        <div className="ia-kpi-label">Target 2</div>
      </div>
      <div className="ia-expansion-block ia-expansion-down">
        <div className="ia-kpi-label">Break Below {support}</div>
        <div className="ia-kpi-value ia-expansion-zone">{breakBelowPrimary}</div>
        <div className="ia-kpi-label">Target 1</div>
        <div className="ia-kpi-value ia-expansion-zone">{breakBelowExtended}</div>
        <div className="ia-kpi-label">Target 2</div>
      </div>
    </div>
  );
}
