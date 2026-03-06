type MarketPlaybookCardProps = {
  bias: string;
  regime?: string;
  plan: string;
  support: string;
  resistance: string;
  expansionTarget?: string;
};

export default function MarketPlaybookCard({
  bias,
  regime,
  plan,
  support,
  resistance,
  expansionTarget,
}: MarketPlaybookCardProps) {
  return (
    <div className="ia-card ia-playbook-card">
      <h3 className="ia-card-title">Intraday Playbook</h3>
      <div className="ia-kpi-grid">
        <div>
          <div className="ia-kpi-label">Bias</div>
          <div className="ia-kpi-value ia-emphasis-high">{bias}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Regime</div>
          <div className="ia-kpi-value">{regime ?? "-"}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Plan</div>
          <div className="ia-kpi-value">{plan}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Support</div>
          <div className="ia-level-support ia-emphasis-high">{support}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Resistance</div>
          <div className="ia-level-resistance ia-emphasis-high">{resistance}</div>
        </div>
        <div>
          <div className="ia-kpi-label">Expansion Target</div>
          <div className="ia-kpi-value ia-emphasis-medium">{expansionTarget ?? "-"}</div>
        </div>
      </div>
    </div>
  );
}
