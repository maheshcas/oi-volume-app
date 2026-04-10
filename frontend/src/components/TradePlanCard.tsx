type TradePlanCardProps = {
  bias: string;
  regime?: string;
  plan: string;
  trapRisk: string;
  executionMode?: string;
  entryZone?: string;
  stopZone?: string;
  targetZone?: string;
  deltaGuidance?: string;
  bullishTrigger?: string;
  bearishTrigger?: string;
  invalidation?: string;
};

export default function TradePlanCard({
  plan,
  executionMode,
  entryZone,
  stopZone,
  targetZone,
  deltaGuidance,
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
        <div className="ia-kpi-label">Execution Mode</div>
        <div className="ia-playbook-trigger">{executionMode ?? "Selective execution"}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Entry Zone</div>
        <div className="ia-playbook-trigger">{entryZone ?? bullishTrigger ?? "Acceptance above active resistance."}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Stop Zone</div>
        <div className="ia-playbook-trigger">{stopZone ?? bearishTrigger ?? "Break below active support."}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Target Zone</div>
        <div className="ia-playbook-trigger">{targetZone ?? invalidation ?? "Wait for clean target confirmation."}</div>
      </div>
      <div className="ia-playbook-line">
        <div className="ia-kpi-label">Delta Guide</div>
        <div className="ia-playbook-trigger">{deltaGuidance ?? "Avoid buying premium in no-edge conditions."}</div>
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
