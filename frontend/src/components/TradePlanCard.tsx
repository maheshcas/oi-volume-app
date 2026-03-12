type TradePlanCardProps = {
  bias: string;
  regime?: string;
  plan: string;
  trapRisk: string;
  bullishTrigger?: string;
  bearishTrigger?: string;
  invalidation?: string;
};

export default function TradePlanCard({
  plan,
  bullishTrigger,
  bearishTrigger,
  invalidation,
}: TradePlanCardProps) {
  return (
    <div className="ia-card ia-playbook-card">
      <h3 className="ia-card-title">Trade Plan</h3>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Primary Plan</div>
        <div className="ia-playbook-plan">{plan}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Bullish Trigger</div>
        <div className="ia-playbook-trigger">{bullishTrigger ?? 'Acceptance above active resistance.'}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Bearish Trigger</div>
        <div className="ia-playbook-trigger">{bearishTrigger ?? 'Break below active support.'}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Invalidation</div>
        <div className="ia-playbook-trigger">{invalidation ?? 'Range compression breaks.'}</div>
      </div>
    </div>
  );
}
