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

type LevelTone = { tone: "low" | "moderate" | "high"; label: TrapLevel };

const toneFor = (level: TrapLevel): LevelTone =>
  level === "High"
    ? { tone: "high", label: "High" }
    : level === "Low"
      ? { tone: "low", label: "Low" }
      : { tone: "moderate", label: "Moderate" };

function resolveDirectionalContext(
  direction: "upside" | "downside" | "",
  spot: number | null | undefined,
  resistance: number | null | undefined,
  trapZone: number,
  probability: number,
  trapMessage: string | null | undefined,
): { title: string; sub: string; arrow: "up" | "down" | "flat" } | null {
  const hasSpot = typeof spot === "number" && Number.isFinite(spot);
  const hasR = typeof resistance === "number" && Number.isFinite(resistance);
  const aboveR = hasSpot && hasR && (spot as number) > (resistance as number);
  const level = trapZone.toLocaleString("en-IN");

  if (aboveR && probability < 50 && hasR) {
    return {
      title: `Breakout above ${(resistance as number).toLocaleString("en-IN")}`,
      sub: "Low trap risk · watch for acceptance",
      arrow: "up",
    };
  }
  if (aboveR && probability >= 50 && hasR) {
    return {
      title: `False breakout risk above ${(resistance as number).toLocaleString("en-IN")}`,
      sub: `Trap ${probability}% · watch for reversal`,
      arrow: "up",
    };
  }
  if (direction === "downside") {
    return {
      title: `Resistance rejection at ${level}`,
      sub: "Watch for reversal back into range",
      arrow: "down",
    };
  }
  if (direction === "upside") {
    return {
      title: `Support absorption at ${level}`,
      sub: "Watch for bounce or breakdown follow-through",
      arrow: "up",
    };
  }
  const msg = String(trapMessage || "").trim();
  if (msg) {
    return { title: msg, sub: "", arrow: "flat" };
  }
  return null;
}

function resolveOiMatrixRow(
  signal: string | null | undefined,
  reason: string | null | undefined,
  confidence: string | null | undefined,
  breachLevel: number | null | undefined,
  breachOiConfirming: boolean | undefined,
  oiPriceDivergence: boolean | undefined,
): { label: string; text: string; tone: "trap" | "confirm" | "neutral" } | null {
  const code = String(signal || "").toUpperCase();
  const isTrap = code === "BULL_TRAP" || code === "BEAR_TRAP";
  const isConfirm = code === "BULL_CONFIRM" || code === "BEAR_CONFIRM";

  if (!isTrap && !isConfirm) return null;

  const label = isTrap ? "OI Trap Confirmed" : "OI Confirms Move";
  const baseText =
    reason || "OI and price are aligned with the detected pattern.";

  const tail: string[] = [];
  if (confidence) tail.push(`confidence ${confidence.toLowerCase()}`);
  if (breachLevel != null) {
    tail.push(
      `level ${Number(breachLevel).toLocaleString("en-IN")} · OI ${
        breachOiConfirming ? "confirming" : "diverging"
      }${oiPriceDivergence ? " · divergence" : ""}`,
    );
  }

  const text = tail.length > 0 ? `${baseText} (${tail.join(" · ")})` : baseText;
  return { label, text, tone: isTrap ? "trap" : "confirm" };
}

function resolveSupportReason(reason: string | null | undefined): {
  tone: "positive" | "negative" | "neutral";
  text: string;
} | null {
  const t = String(reason || "").trim();
  if (!t) return null;
  const lower = t.toLowerCase();
  if (/strengthen|defending|strong|building|holding/i.test(lower))
    return { tone: "positive", text: t };
  if (/weaken|exposed|break|fail|thin|vulnerable/i.test(lower))
    return { tone: "negative", text: t };
  return { tone: "neutral", text: t };
}

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
  key_range,
}: TrapCardProps) {
  void trap_type;
  void institutional_levels_noop;
  const probability = Math.max(0, Math.min(100, Math.round(trap_probability)));
  const resolvedLevel = (["Low", "Moderate", "High"] as TrapLevel[]).includes(trap_level)
    ? trap_level
    : "Moderate";
  const levelTone = toneFor(resolvedLevel);

  const directional = resolveDirectionalContext(
    trap_direction,
    spot,
    resistance,
    trap_zone,
    probability,
    trap_message,
  );

  const oiMatrix = resolveOiMatrixRow(
    oi_trap_signal,
    oi_trap_reason,
    oi_trap_confidence,
    breach_level,
    breach_oi_confirming,
    oi_price_divergence,
  );

  const supportContext = resolveSupportReason(support_reason);
  const hasAbsorption = Boolean(absorption_detected) && Boolean(absorption_message);
  const hasContextRows =
    Boolean(key_range) || hasAbsorption || Boolean(supportContext) || Boolean(oiMatrix) || Boolean(trap_reason);

  return (
    <section className={`trap-card trap-card-v2 trap-card-v2-${levelTone.tone}`}>
      <div className="trap-v2-header">
        <div className="trap-v2-eyebrow">Trap</div>
        <div className="trap-v2-state">
          <span className="trap-v2-state-dot" />
          <span className="trap-v2-state-label">{levelTone.label}</span>
        </div>
      </div>

      <div className="trap-v2-hero">
        <span className="trap-v2-pct">{probability}%</span>
        <span className="trap-v2-pct-sub">false-break risk</span>
      </div>

      <div className="trap-v2-bar" aria-hidden="true">
        <div className="trap-v2-bar-fill" style={{ width: `${probability}%` }} />
        <div className="trap-v2-bar-gate" title="55% blocking threshold" />
      </div>

      {directional ? (
        <div className={`trap-v2-directional trap-v2-directional-${directional.arrow}`}>
          <span className="trap-v2-directional-arrow">
            {directional.arrow === "up" ? "↑" : directional.arrow === "down" ? "↓" : "◈"}
          </span>
          <div className="trap-v2-directional-body">
            <div className="trap-v2-directional-title">{directional.title}</div>
            {directional.sub ? (
              <div className="trap-v2-directional-sub">{directional.sub}</div>
            ) : null}
          </div>
        </div>
      ) : null}

      {suggested_action ? (
        <div className="trap-v2-recommended">
          <div className="trap-v2-recommended-label">Recommended</div>
          <div className="trap-v2-recommended-body">{suggested_action}</div>
        </div>
      ) : null}

      {hasContextRows ? (
        <div className="trap-v2-context">
          {key_range ? (
            <div className="trap-v2-ctx-row">
              <span className="trap-v2-ctx-key">Key range</span>
              <span className="trap-v2-ctx-val">{key_range}</span>
            </div>
          ) : null}

          {supportContext ? (
            <div className="trap-v2-ctx-row">
              <span className="trap-v2-ctx-key">Support</span>
              <span className={`trap-v2-ctx-val trap-v2-ctx-val-${supportContext.tone}`}>
                {supportContext.text}
              </span>
            </div>
          ) : null}

          {trap_reason ? (
            <div className="trap-v2-ctx-row">
              <span className="trap-v2-ctx-key">OI imbalance</span>
              <span className="trap-v2-ctx-val">{trap_reason}</span>
            </div>
          ) : null}

          {oiMatrix ? (
            <div className={`trap-v2-ctx-row trap-v2-ctx-row-${oiMatrix.tone}`}>
              <span className="trap-v2-ctx-key">{oiMatrix.label}</span>
              <span className="trap-v2-ctx-val">{oiMatrix.text}</span>
            </div>
          ) : null}

          {hasAbsorption ? (
            <div className="trap-v2-ctx-row trap-v2-ctx-row-accent">
              <span className="trap-v2-ctx-key">Absorption</span>
              <span className="trap-v2-ctx-val">{absorption_message}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

const institutional_levels_noop = undefined;
