type TrapLevel = "Low" | "Moderate" | "High";

export type TrapCardProps = {
  trap_probability: number;
  trap_level: TrapLevel;
  trap_type: string;
  trap_zone: number;
  suggested_action: string;
  show_affected_level?: boolean;
};

const levelStyles: Record<TrapLevel, { chip: string; bar: string; glow: string }> = {
  Low: {
    chip: "trap-chip-low",
    bar: "trap-bar-low",
    glow: "trap-glow-low",
  },
  Moderate: {
    chip: "trap-chip-moderate",
    bar: "trap-bar-moderate",
    glow: "trap-glow-moderate",
  },
  High: {
    chip: "trap-chip-high",
    bar: "trap-bar-high",
    glow: "trap-glow-high",
  },
};

export default function TrapCard({
  trap_probability,
  trap_level,
  trap_type,
  trap_zone,
  suggested_action,
  show_affected_level = true,
}: TrapCardProps) {
  const probability = Math.max(0, Math.min(100, Math.round(trap_probability)));
  const style = levelStyles[trap_level];

  return (
    <section className={`trap-card ${style.glow}`}>
      <div className="trap-card-head">
        <h3 className="trap-card-title">Trap Risk</h3>
        <span className={`trap-chip ${style.chip}`}>
          {trap_level}
        </span>
      </div>

      <div className="trap-metric">
        <div className="trap-metric-head">
          <span className="trap-metric-label">Trap Risk %</span>
          <span className="trap-metric-value">{probability}%</span>
        </div>
        <div className="trap-progress">
          <div
            className={`trap-progress-fill ${style.bar}`}
            style={{ width: `${probability}%` }}
          />
        </div>
      </div>

      <dl className="trap-details">
        <div className="trap-row">
          <dt className="trap-key">Trap Type</dt>
          <dd className="trap-value">{trap_type || "-"}</dd>
        </div>
        {show_affected_level ? (
          <div className="trap-row">
            <dt className="trap-key">Affected Level</dt>
            <dd className="trap-value">{trap_zone}</dd>
          </div>
        ) : null}
        <div className="trap-action">
          <dt className="trap-action-key">Suggested Action</dt>
          <dd className="trap-action-value">{suggested_action}</dd>
        </div>
      </dl>
    </section>
  );
}
