type TrapLevel = "Low" | "Moderate" | "High";

export type TrapCardProps = {
  trap_probability: number;
  trap_level: TrapLevel;
  trap_type: string;
  trap_zone: number;
  trap_direction?: "upside" | "downside" | "";
  suggested_action: string;
  trap_reason?: string | null;
  support_reason?: string | null;
  absorption_detected?: boolean;
  absorption_message?: string | null;
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
    accent: "#ff4444",
    surface: "rgba(255, 68, 68, 0.15)",
    border: "rgba(255, 68, 68, 0.24)",
  },
};

export default function TrapCard({
  trap_probability,
  trap_level,
  trap_type,
  trap_zone,
  trap_direction = "",
  suggested_action,
  trap_reason,
  support_reason,
  absorption_detected,
  absorption_message,
  show_affected_level = true,
}: TrapCardProps) {
  const probability = Math.max(0, Math.min(100, Math.round(trap_probability)));
  const resolvedTrapLevel = levelStyles[trap_level] ? trap_level : "Moderate";
  const style = levelStyles[resolvedTrapLevel];
  const isRejection = trap_direction === "downside";
  const trapTypeLabel =
    trap_direction === "downside" && trap_type.toLowerCase().includes("breakout failure")
      ? "Breakdown Failure"
      : trap_type || "-";

  const directionLabel = isRejection ? "Resistance rejection" : "Support absorption";
  const mergedTypeLabel = trapTypeLabel !== "-"
    ? trap_direction ? `${trapTypeLabel} → ${directionLabel}` : trapTypeLabel
    : trap_direction ? directionLabel : "-";

  const affectedLabel = trap_direction === "downside"
    ? `Resistance at risk: ${trap_zone.toLocaleString("en-IN")}`
    : trap_direction === "upside"
      ? `Support at risk: ${trap_zone.toLocaleString("en-IN")}`
      : `Level: ${trap_zone.toLocaleString("en-IN")}`;

  return (
    <section className={`trap-card ${style.glow}`}>
      <div className="trap-header">
        <div className="trap-title-row">
          <span className="trap-lbl">Trap Risk</span>
        </div>

        <div className="trap-pct-row">
          <span className="trap-pct">{probability}%</span>
          <span className={`trap-badge lvl-${resolvedTrapLevel.toLowerCase()}`}>
            {resolvedTrapLevel}
          </span>
        </div>

        <div className="trap-bar-outer">
          <div
            className={`trap-bar-fill ${style.bar}`}
            style={{ width: `${probability}%` }}
          />
        </div>

        <div className="trap-meta-row">
          <span className="trap-type">{mergedTypeLabel}</span>
          {show_affected_level ? (
            <span className="trap-affected">{affectedLabel}</span>
          ) : null}
        </div>
      </div>

      <div className="trap-details">
        {absorption_detected && absorption_message ? (
          <div
            className="trap-row trap-row-accent"
            style={{ background: style.surface, borderColor: style.border }}
          >
            <div className="trap-key" style={{ color: style.accent }}>Absorption Alert</div>
            <div className="trap-value">{absorption_message}</div>
          </div>
        ) : null}

        {trap_reason ? (
          <div className="trap-row">
            <div className="trap-key">OI Imbalance Trap</div>
            <div className="trap-value">{trap_reason}</div>
          </div>
        ) : null}

        {support_reason ? (
          <div className="trap-row">
            <div className="trap-key">Support Strength</div>
            <div className="trap-value">{support_reason}</div>
          </div>
        ) : null}

        <div
          className="trap-action-box"
          style={{ borderColor: style.border }}
        >
          <div className="trap-action-key">Suggested Action</div>
          <div className="trap-action-value">{suggested_action}</div>
        </div>
      </div>
    </section>
  );
}
