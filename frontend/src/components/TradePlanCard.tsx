type TradePlanCardProps = {
  bias: string;
  regime?: string;
  plan: string;
  trapRisk: string;
};

export default function TradePlanCard({
  bias,
  regime,
  plan,
  trapRisk,
}: TradePlanCardProps) {
  return (
    <div className="ia-card ia-playbook-card">
      <h3 className="ia-card-title">Trade Plan</h3>
      <div className="ia-playbook-plan">{plan}</div>
      <div className="ia-playbook-tags">
        <span className="ia-status-chip">Bias: {bias}</span>
        <span className="ia-status-chip">Regime: {regime ?? "-"}</span>
        <span className="ia-status-chip">Trap Risk: {trapRisk}</span>
      </div>
    </div>
  );
}
