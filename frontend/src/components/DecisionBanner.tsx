import {
  confidenceLabel,
  friendlyBlockingReason,
  friendlyWinningEngine,
} from "./decisionUx";

type DecisionBannerProps = {
  action: "WAIT" | "CAUTION" | "READY";
  direction: "Bullish" | "Bearish" | "Neutral" | "Conflict";
  explanation: string;
  bias: string;
  readinessScore: number;
  readinessState: string;
  pressureState: string;
  regime: string;
  detailSummary?: string;
  detailInsight?: string;
  detailWalls?: string | null;
  support: string;
  resistance: string;
  blockingReason?: string;
  winningEngine?: string;
  decisionConfidence?: number | null;
  supportTransitionBadge?: boolean;
  resistanceTransitionBadge?: boolean;
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
  bias,
  readinessScore,
  readinessState,
  pressureState,
  regime,
  detailSummary,
  detailInsight,
  detailWalls,
  support: _support,
  resistance: _resistance,
  blockingReason = "NONE",
  winningEngine = "none",
  decisionConfidence = null,
  supportTransitionBadge = false,
  resistanceTransitionBadge = false,
}: DecisionBannerProps) {
  const displayExplanation = normalizeExplanation(action, direction, explanation);
  const toneClass =
    action === "READY"
      ? "ia-decision-banner-ready"
      : action === "CAUTION"
        ? "ia-decision-banner-caution"
        : "ia-decision-banner-wait";
  const readinessPct = Math.max(0, Math.min(100, Number(readinessScore) || 0));
  const confidencePct = Math.max(0, Math.min(100, Number(decisionConfidence) || 0));
  const biasLabel = bias || formatDirectionLabel(direction);
  const readinessStateClass =
    readinessState.toLowerCase().includes("high") || readinessState.toLowerCase().includes("active")
      ? "ia-text-bull"
      : readinessState.toLowerCase().includes("low")
        ? "ia-text-bear"
        : "ia-text-warn";
  const pressureLabel = pressureState.replace(/\s*Pressure$/i, "").trim() || pressureState;
  const confidenceTone = confidenceLabel(decisionConfidence);
  const transitionLabel = supportTransitionBadge
    ? "Support Transition Active"
    : resistanceTransitionBadge
      ? "Resistance Transition Active"
      : null;
  const showBlocker = blockingReason && blockingReason !== "NONE";

  return (
    <div className={`ia-card ia-decision-banner ia-decision-banner-v2 ${toneClass}`}>
      <div className="ia-decision-banner-v2-head">
        <div className="ia-kpi-label ia-decision-banner-v2-title">Trade Signal</div>
        <div className="ia-decision-banner-v2-badge">{action}</div>
      </div>

      <div className="ia-decision-banner-v2-body">
        <div className="ia-decision-banner-explanation">{displayExplanation}</div>

        <div className="ia-decision-meta-row">
          {showBlocker ? (
            <span className="ia-decision-meta-chip ia-decision-meta-chip-blocker">
              Blocker: {friendlyBlockingReason(blockingReason)}
            </span>
          ) : null}
          <span className="ia-decision-meta-chip">{friendlyWinningEngine(winningEngine)}</span>
          {transitionLabel ? (
            <span className="ia-decision-meta-chip ia-decision-meta-chip-transition">{transitionLabel}</span>
          ) : null}
        </div>

        <div className="ia-readiness-wrap">
          <div className="ia-readiness-row">
            <span className="ia-readiness-label">Trade Readiness</span>
            <span className="ia-readiness-value">{Math.round(readinessPct)}%</span>
          </div>
          <div className="ia-readiness-track">
            <div className="ia-readiness-fill" style={{ width: `${readinessPct}%` }} />
            <div className="ia-readiness-threshold-wrap" style={{ left: "57%" }}>
              <span className="ia-readiness-entry">57 entry</span>
              <div className="ia-readiness-threshold" />
            </div>
          </div>
        </div>

        <div className="ia-confidence-strip">
          <div className="ia-confidence-head">
            <span className="ia-decision-grid-label">Decision Confidence</span>
            <span className={`ia-confidence-chip ia-confidence-chip-${confidenceTone.toLowerCase()}`}>
              {Math.round(confidencePct)}% {confidenceTone}
            </span>
          </div>
          <div className="ia-confidence-track">
            <div className="ia-confidence-fill" style={{ width: `${confidencePct}%` }} />
          </div>
        </div>

        <div className="ia-decision-grid">
          <div className="ia-decision-grid-item">
            <div className="ia-decision-grid-label">Bias</div>
            <div className="ia-decision-grid-value ia-text-muted">{biasLabel}</div>
          </div>
          <div className="ia-decision-grid-item">
            <div className="ia-decision-grid-label">Pressure</div>
            <div className="ia-decision-grid-value ia-text-muted">{pressureLabel}</div>
          </div>
          <div className="ia-decision-grid-item">
            <div className="ia-decision-grid-label">Regime</div>
            <div className="ia-decision-grid-value">{regime || "-"}</div>
          </div>
          <div className="ia-decision-grid-item">
            <div className="ia-decision-grid-label">Readiness State</div>
            <div className={`ia-decision-grid-value ${readinessStateClass}`}>{readinessState || "-"}</div>
          </div>
        </div>

        {(detailSummary || detailInsight || detailWalls) ? (
          <details className="ia-decision-more">
            <summary>More detail</summary>
            <div className="ia-decision-more-body">
              {detailSummary ? (
                <div className="ia-decision-more-block">
                  <div className="ia-decision-more-label">Key Range</div>
                  <div className="ia-decision-more-text">{detailSummary}</div>
                </div>
              ) : null}
              {detailWalls ? (
                <div className="ia-decision-more-block">
                  <div className="ia-decision-more-label">Institutional Levels</div>
                  <div className="ia-decision-more-text">{detailWalls}</div>
                </div>
              ) : null}
              {detailInsight ? (
                <div className="ia-decision-more-block">
                  <div className="ia-decision-more-label">Market Insight</div>
                  <div className="ia-decision-more-text">{detailInsight}</div>
                </div>
              ) : null}
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}
