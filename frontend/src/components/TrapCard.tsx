type TrapLevel = "Low" | "Moderate" | "High";

export type TrapCardProps = {
  trap_probability: number;
  trap_level: TrapLevel;
  trap_type: string;
  trap_zone: number;
  trap_message?: string | null;
  spot?: number | null;
  resistance?: number | null;
  trap_direction?: "upside" | "downside" | "";
  suggested_action: string;
  trap_reason?: string | null;
  support_reason?: string | null;
  oi_trap_signal?: string | null;
  oi_trap_confidence?: string | null;
  oi_trap_reason?: string | null;
  breach_level?: number | null;
  breach_oi_confirming?: boolean;
  oi_price_divergence?: boolean;
  absorption_detected?: boolean;
  absorption_message?: string | null;
  show_affected_level?: boolean;
  key_range?: string | null;
  institutional_levels?: string | null;
  market_insight?: string | null;
  putWall?: number;
  callWall?: number;
  oi_scenario?: string;
};

const oiScenarioLabel = (scenario: string): string =>
  ({
    LONG_BUILDUP: "Fresh longs building — buyers in control",
    SHORT_BUILDUP: "Fresh shorts building — sellers in control",
    SHORT_COVERING: "Shorts covering — move may be exhausted",
    LONG_UNWINDING: "Longs exiting — weakness, watch for reversal",
    PINNING: "Both sides writing — market pinned to range",
    NEUTRAL: "",
  })[scenario] ?? scenario;

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
  trap_message,
  spot,
  resistance,
  trap_direction = "",
  suggested_action,
  trap_reason,
  support_reason,
  oi_trap_signal,
  oi_trap_confidence,
  oi_trap_reason,
  breach_level,
  breach_oi_confirming,
  oi_price_divergence,
  absorption_detected,
  absorption_message,
  show_affected_level = true,
  key_range,
  institutional_levels,
  market_insight,
  putWall,
  callWall,
  oi_scenario,
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
    : "No active trap";

  const affectedLabel = trap_direction === "downside"
    ? `Resistance at risk: ${trap_zone.toLocaleString("en-IN")}`
    : trap_direction === "upside"
      ? `Support at risk: ${trap_zone.toLocaleString("en-IN")}`
      : `Level: ${trap_zone.toLocaleString("en-IN")}`;
  const oiSignal = String(oi_trap_signal || "NEUTRAL").toUpperCase();
  const showOiRow = Boolean(oiSignal);
  const oiIsTrap = oiSignal === "BULL_TRAP" || oiSignal === "BEAR_TRAP";
  const oiIsConfirm = oiSignal === "BULL_CONFIRM" || oiSignal === "BEAR_CONFIRM";
  const aboveResistance =
    typeof spot === "number" &&
    Number.isFinite(spot) &&
    typeof resistance === "number" &&
    Number.isFinite(resistance) &&
    spot > resistance;
  const trapMessage = aboveResistance && probability < 50 && typeof resistance === "number"
    ? `Breakout above ${resistance.toLocaleString("en-IN")} - low trap risk, watch for acceptance`
    : aboveResistance && probability >= 50 && typeof resistance === "number"
      ? `False breakout risk above ${resistance.toLocaleString("en-IN")} - trap ${probability}%`
      : String(trap_message || "").trim();

  return (
    <section className={`trap-card ${style.glow}`}>
      {(putWall || callWall || oi_scenario) ? (
        <div className="ia-oi-brief">
          {putWall ? (
            <div className="ia-oi-brief-row ia-oi-brief-bull">
              <span className="ia-oi-brief-icon">↑</span>
              <span>Put Wall {putWall.toLocaleString("en-IN")} — floor defended</span>
            </div>
          ) : null}
          {callWall ? (
            <div className="ia-oi-brief-row ia-oi-brief-bear">
              <span className="ia-oi-brief-icon">↓</span>
              <span>Call Wall {callWall.toLocaleString("en-IN")} — ceiling active</span>
            </div>
          ) : null}
          {oi_scenario && oi_scenario !== "NEUTRAL" ? (
            <div className="ia-oi-brief-row ia-oi-brief-neutral">
              <span className="ia-oi-brief-icon">◈</span>
              <span>{oiScenarioLabel(oi_scenario)}</span>
            </div>
          ) : null}
        </div>
      ) : null}

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
        {key_range ? (
          <div className="trap-row">
            <div className="trap-key">Key Range</div>
            <div className="trap-value">{key_range}</div>
          </div>
        ) : null}

        {institutional_levels ? (
          <div className="trap-row">
            <div className="trap-key">Institutional Levels</div>
            <div className="trap-value">{institutional_levels}</div>
          </div>
        ) : null}

        {market_insight ? (
          <div className="trap-row">
            <div className="trap-key">Market Insight</div>
            <div className="trap-value">{market_insight}</div>
          </div>
        ) : null}

        {trapMessage ? (
          <div className="trap-row">
            <div className="trap-key">Trap Context</div>
            <div className="trap-value">{trapMessage}</div>
          </div>
        ) : null}

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

        {showOiRow ? (
          <div className="trap-row trap-row-accent">
            <div className="trap-key">
              <span className={`trap-oi-pill ${oiIsTrap ? "trap-oi-pill-trap" : oiIsConfirm ? "trap-oi-pill-confirm" : ""}`}>
                {oiIsTrap ? "OI Trap Confirmed" : oiIsConfirm ? "OI Confirms Move" : "OI Matrix"}
              </span>
            </div>
            <div className="trap-value">
              {oi_trap_reason || "OI and price are not in a clear trap/confirm pattern."}
              {oi_trap_confidence ? <div className="trap-oi-confidence">Confidence: {oi_trap_confidence}</div> : null}
              {breach_level ? (
                <div className="trap-oi-extra">
                  Level {Number(breach_level).toLocaleString("en-IN")} · OI {breach_oi_confirming ? "confirming" : "diverging"}
                  {oi_price_divergence ? " · divergence" : ""}
                </div>
              ) : null}
            </div>
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
