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
        <div className="ia-kpi-value">→ {breakAbovePrimary}</div>
        <div className="ia-kpi-value">→ {breakAboveExtended}</div>
      </div>
      <div className="ia-expansion-block ia-expansion-down">
        <div className="ia-kpi-label">Break Below {support}</div>
        <div className="ia-kpi-value">→ {breakBelowPrimary}</div>
        <div className="ia-kpi-value">→ {breakBelowExtended}</div>
      </div>
    </div>
  );
}

