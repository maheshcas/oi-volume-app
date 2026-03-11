type TrapLevel = "Low" | "Moderate" | "High";

export type TrapCardProps = {
  trap_probability: number;
  trap_level: TrapLevel;
  trap_type: string;
  trap_zone: number;
  suggested_action: string;
  trap_reason?: string | null;
  support_reason?: string | null;
  show_affected_level?: boolean;
};

const levelStyles: Record<
  TrapLevel,
  {
    chip: string;
    bar: string;
    glow: string;
    accent: string;
    surface: string;
    border: string;
  }
> = {
  Low: {
    chip: "trap-chip-low",
    bar: "trap-bar-low",
    glow: "trap-glow-low",
    accent: "#9ca3af",
    surface: "rgba(148, 163, 184, 0.10)",
    border: "rgba(148, 163, 184, 0.24)",
  },
  Moderate: {
    chip: "trap-chip-moderate",
    bar: "trap-bar-moderate",
    glow: "trap-glow-moderate",
    accent: "#f59e0b",
    surface: "rgba(245, 158, 11, 0.10)",
    border: "rgba(245, 158, 11, 0.24)",
  },
  High: {
    chip: "trap-chip-high",
    bar: "trap-bar-high",
    glow: "trap-glow-high",
    accent: "#ef4444",
    surface: "rgba(239, 68, 68, 0.10)",
    border: "rgba(239, 68, 68, 0.24)",
  },
};

export default function TrapCard({
  trap_probability,
  trap_level,
  trap_type,
  trap_zone,
  suggested_action,
  trap_reason,
  support_reason,
  show_affected_level = true,
}: TrapCardProps) {
  const probability = Math.max(0, Math.min(100, Math.round(trap_probability)));
  const style = levelStyles[trap_level];

  return (
    <section className={`trap-card ${style.glow}`}>
      <div className="trap-card-head">
        <h3 className="trap-card-title">Trap Risk</h3>
        <span
          className={`trap-chip ${style.chip}`}
          style={{
            background: style.surface,
            borderColor: style.border,
            color: style.accent,
          }}
        >
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
            style={{ width: `${probability}%`, background: style.accent }}
          />
        </div>
      </div>

      <div className="trap-details" style={{ display: "grid", gap: 10 }}>
        <div
          className="trap-row"
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: `1px solid ${style.border}`,
            background: style.surface,
          }}
        >
          <div className="trap-key" style={{ marginBottom: 4 }}>Trap Risk Level</div>
          <div className="trap-value" style={{ color: style.accent, fontWeight: 800, fontSize: 18 }}>
            {trap_level}
          </div>
        </div>

        <div className="trap-row" style={{ padding: "10px 12px", borderRadius: 12, background: "rgba(255,255,255,0.03)" }}>
          <div className="trap-key" style={{ marginBottom: 4 }}>Trap Type</div>
          <div className="trap-value" style={{ fontWeight: 700 }}>{trap_type || "-"}</div>
        </div>

        {trap_reason ? (
          <div className="trap-row" style={{ padding: "10px 12px", borderRadius: 12, background: "rgba(255,255,255,0.03)" }}>
            <div className="trap-key" style={{ marginBottom: 4 }}>OI Imbalance Trap</div>
            <div className="trap-value" style={{ fontWeight: 700, lineHeight: 1.5 }}>{trap_reason}</div>
          </div>
        ) : null}

        {support_reason ? (
          <div className="trap-row" style={{ padding: "10px 12px", borderRadius: 12, background: "rgba(255,255,255,0.03)" }}>
            <div className="trap-key" style={{ marginBottom: 4 }}>Support Strength</div>
            <div className="trap-value" style={{ fontWeight: 700, lineHeight: 1.5 }}>{support_reason}</div>
          </div>
        ) : null}

        {show_affected_level ? (
          <div className="trap-row" style={{ padding: "10px 12px", borderRadius: 12, background: "rgba(255,255,255,0.03)" }}>
            <div className="trap-key" style={{ marginBottom: 4 }}>Affected Level</div>
            <div className="trap-value">{trap_zone}</div>
          </div>
        ) : null}

        <div
          className="trap-action"
          style={{
            padding: "12px",
            borderRadius: 12,
            border: `1px solid ${style.border}`,
            background: "rgba(255,255,255,0.04)",
          }}
        >
          <div className="trap-action-key" style={{ marginBottom: 6 }}>Suggested Action</div>
          <div className="trap-action-value" style={{ lineHeight: 1.5, fontWeight: 600 }}>
            {suggested_action}
          </div>
        </div>
      </div>
    </section>
  );
}
