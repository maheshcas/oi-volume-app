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
  const directionSymbol =
    trap_direction === "downside"
      ? "\u2191"
      : trap_direction === "upside"
        ? "\u2193"
        : "\u2014";
  const trapTypeLabel =
    trap_direction === "downside" && trap_type.toLowerCase().includes("breakout failure")
      ? "Breakdown Failure"
      : trap_type || "-";

  return (
    <section className={`trap-card ${style.glow}`}>
      <div className="trap-header">
        <div className="trap-title-row">
          <span className="trap-lbl">Trap Risk</span>
          {trap_direction ? (
            <span className={`dir-pill ${isRejection ? "dp-rejection" : "dp-absorption"}`}>
              <span className="dir-arrow">{directionSymbol}</span>
              <span>{isRejection ? "Resistance rejection" : "Support absorption"}</span>
            </span>
          ) : null}
        </div>

        <div className="trap-pct-row">
          <span className="trap-pct">{probability}%</span>
          <span
            className={`trap-badge lvl-${resolvedTrapLevel.toLowerCase()}`}
            style={{
              background: style.surface,
              borderColor: resolvedTrapLevel === "High" ? "rgba(255, 68, 68, 0.30)" : style.border,
              color: style.accent,
            }}
          >
            {resolvedTrapLevel}
          </span>
        </div>

        <div className="trap-bar-outer">
          <div
            className={`trap-bar-fill ${style.bar}`}
            style={{ width: `${probability}%`, background: resolvedTrapLevel === "High" ? "#ff4444" : style.accent, opacity: resolvedTrapLevel === "High" ? 0.8 : 1 }}
          />
        </div>

        <div className="trap-meta-row">
          <span className="trap-type">{trapTypeLabel}</span>
          {show_affected_level ? (
            <span className="trap-affected">
              Affected {trap_zone.toLocaleString("en-IN")}
            </span>
          ) : null}
        </div>
      </div>

      <div className="trap-details" style={{ display: "grid", gap: 10 }}>
        {trap_reason ? (
          <div className="trap-row" style={{ padding: "8px 12px", borderRadius: 12, background: "rgba(255,255,255,0.03)" }}>
            <div className="trap-key" style={{ marginBottom: 4 }}>OI Imbalance Trap</div>
            <div className="trap-value" style={{ fontWeight: 700, lineHeight: 1.5 }}>{trap_reason}</div>
          </div>
        ) : null}

        {support_reason ? (
          <div className="trap-row" style={{ padding: "8px 12px", borderRadius: 12, background: "rgba(255,255,255,0.03)" }}>
            <div className="trap-key" style={{ marginBottom: 4 }}>Support Strength</div>
            <div className="trap-value" style={{ fontWeight: 700, lineHeight: 1.5 }}>{support_reason}</div>
          </div>
        ) : null}
        {absorption_detected && absorption_message ? (
          <div
            className="trap-row"
            style={{
              padding: "8px 12px",
              borderRadius: 12,
              background: style.surface,
              border: `1px solid ${style.border}`,
            }}
          >
            <div className="trap-key" style={{ marginBottom: 4, color: style.accent }}>Absorption Alert</div>
            <div className="trap-value" style={{ fontWeight: 700, lineHeight: 1.5 }}>{absorption_message}</div>
          </div>
        ) : null}

        <div
          className="trap-action"
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: `1px solid ${style.border}`,
            background: "rgba(255,255,255,0.04)",
          }}
        >
          <div className="trap-action-key" style={{ marginBottom: 6 }}>Suggested Action</div>
          <div className="trap-action-value" style={{ lineHeight: 1.42, fontWeight: 500 }}>
            {suggested_action}
          </div>
        </div>
      </div>
    </section>
  );
}
