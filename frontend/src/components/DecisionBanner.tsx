type DecisionBannerProps = {
  action: "WAIT" | "CAUTION" | "READY";
  direction: "Bullish" | "Bearish" | "Neutral" | "Conflict";
  explanation: string;
  support: string;
  resistance: string;
};

function formatDirectionLabel(direction: DecisionBannerProps["direction"]) {
  if (direction === "Neutral") return "Neutral Bias";
  if (direction === "Conflict") return "Range Conflict";
  return direction;
}

function normalizeExplanation(
  action: DecisionBannerProps["action"],
  direction: DecisionBannerProps["direction"],
  explanation: string
) {
  const clean = (explanation || "").trim();
  const fallbackWait =
    direction === "Conflict"
      ? "Signals are mixed near key boundaries. Waiting is correct until price confirms one side."
      : direction === "Neutral"
        ? "Directional conviction is weak. Waiting is correct until a cleaner setup forms."
        : `Momentum is not confirmed yet. Waiting is correct until ${direction.toLowerCase()} pressure strengthens.`;

  if (!clean) {
    return action === "WAIT"
      ? fallbackWait
      : action === "CAUTION"
        ? "Setup is forming, but confirmation is still incomplete."
        : "Conditions are aligned for execution.";
  }

  const lower = clean.toLowerCase();

  if (action === "WAIT") {
    if (lower.includes("breakout")) {
      return fallbackWait;
    }
    if (!lower.includes("wait")) {
      return `Waiting is correct: ${clean.charAt(0).toLowerCase()}${clean.slice(1)}`;
    }
  }

  if (action !== "READY" && lower.includes("breakout")) {
    return action === "WAIT"
      ? fallbackWait
      : "Setup is not confirmed yet. Caution is correct until participation improves.";
  }

  return clean;
}

export default function DecisionBanner({
  action,
  direction,
  explanation,
  support: _support,
  resistance: _resistance,
}: DecisionBannerProps) {
  const actionLabel = action === "READY" ? "TRADE" : action;
  const displayExplanation = normalizeExplanation(action, direction, explanation);
  const displayDirection = formatDirectionLabel(direction);
  const toneClass =
    action === "READY"
      ? "ia-decision-banner-ready"
      : action === "CAUTION"
        ? "ia-decision-banner-caution"
        : "ia-decision-banner-wait";

  const directionClass =
    direction === "Bullish"
      ? "ia-text-bull"
      : direction === "Bearish"
        ? "ia-text-bear"
        : direction === "Conflict"
          ? "ia-text-warn"
          : "ia-text-muted";

  return (
    <div
      className={`ia-card ia-decision-banner ${toneClass}`}
      style={{
        padding: 20,
        display: "grid",
        gap: 16,
        borderRadius: 18,
      }}
    >
      <div
        className="ia-decision-banner-header"
        style={{
          display: "grid",
          gap: 6,
        }}
      >
        <div
          className="ia-decision-banner-action"
          style={{
            fontSize: 42,
            lineHeight: 0.95,
            fontWeight: 900,
            letterSpacing: "0.06em",
            color: "#f8fbff",
            textTransform: "uppercase",
          }}
        >
          {actionLabel}
        </div>
        <div
          className={`ia-decision-banner-direction ${directionClass}`}
          style={{
            fontSize: 24,
            lineHeight: 1.1,
            fontWeight: 700,
          }}
        >
          {displayDirection}
        </div>
      </div>

      <div
        className="ia-decision-banner-explanation"
        style={{
          fontSize: 15,
          lineHeight: 1.5,
          color: "#d7e3f2",
          maxWidth: "54ch",
        }}
      >
        {displayExplanation}
      </div>
    </div>
  );
}
