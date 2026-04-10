import {
  confidenceLabel,
  friendlyBlockingReason,
  friendlyWinningEngine,
} from "./decisionUx";

type DecisionBannerProps = {
  action: "WAIT" | "CAUTION" | "READY";
  direction: "Bullish" | "Bearish" | "Neutral" | "Conflict";
  explanation: string;
  sessionPhase?: string | null;
  bias: string;
  readinessScore: number;
  readinessState: string;
  readinessExplainability?: string | null;
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

function formatActionBadge(action: string, sessionPhase?: string | null) {
  const phase = String(sessionPhase || "").trim();
  if (action === "WAIT" && phase) {
    return `${action} - ${phase}`;
  }
  return action;
}

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
      const normalizedLead =
        /^[A-Z]{2,}\b/.test(clean) || !clean
          ? clean
          : `${clean.charAt(0).toLowerCase()}${clean.slice(1)}`;
      return `Waiting is correct: ${normalizedLead}`;
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
  sessionPhase = null,
  bias,
  readinessScore,
  readinessState,
  readinessExplainability = null,
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
  const actionBadge = formatActionBadge(action, sessionPhase);
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
  const hasBlocker = blockingReason && blockingReason !== "NONE";
  const showBlocker = false;
  const dominantMessage = hasBlocker
    ? `${friendlyBlockingReason(blockingReason)} - ${action}`
    : displayExplanation;
  return (
    <div className={`ia-card ia-decision-banner ia-decision-banner-v2 ${toneClass}`}>
      <div className="ia-decision-banner-v2-head">
        <div className="ia-kpi-label ia-decision-banner-v2-title">Trade Signal</div>
        <div className="ia-decision-banner-v2-head-actions">
          <div className="ia-decision-banner-v2-badge">{actionBadge}</div>
        </div>
      </div>

      <div className="ia-decision-banner-v2-body">
        {showBlocker ? (
          <div className="ia-decision-blocker-bar">
            ⛔ Blocked: {friendlyBlockingReason(blockingReason)}
          </div>
        ) : null}

        <div className="ia-decision-banner-explanation">{dominantMessage}</div>

        <div className="ia-decision-meta-row">
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
          <div
            className="ia-readiness-track"
            role="progressbar"
            aria-valuenow={Math.round(readinessPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Trade readiness"
          >
            <div className="ia-readiness-fill" style={{ width: `${readinessPct}%` }} />
            <div className="ia-readiness-threshold-wrap" style={{ left: "60%" }}>
              <span className="ia-readiness-entry">60% min. entry</span>
              <div className="ia-readiness-threshold" />
            </div>
          </div>
        </div>
        {readinessExplainability ? (
          <div className="ia-readiness-explain">{readinessExplainability}</div>
        ) : null}

        <div className="ia-confidence-strip">
          <div className="ia-confidence-head">
            <span className="ia-decision-grid-label">Decision Confidence</span>
            <span className={`ia-confidence-chip ia-confidence-chip-${confidenceTone.toLowerCase()}`}>
              {Math.round(confidencePct)}% {confidenceTone}
            </span>
          </div>
        </div>

        <div className="ia-decision-grid">
          <div className="ia-decision-grid-item ia-decision-grid-item-primary">
            <div className="ia-decision-grid-label">Bias</div>
            <div className="ia-decision-grid-value">{biasLabel}</div>
          </div>
          <div className="ia-decision-grid-item ia-decision-grid-item-primary">
            <div className="ia-decision-grid-label">Pressure</div>
            <div className="ia-decision-grid-value">{pressureLabel}</div>
          </div>
          <div className="ia-decision-grid-item">
            <div className="ia-decision-grid-label">Regime</div>
            <div className="ia-decision-grid-value ia-text-muted">{regime || "-"}</div>
          </div>
          <div className="ia-decision-grid-item">
            <div className="ia-decision-grid-label">Readiness State</div>
            <div className={`ia-decision-grid-value ia-text-muted ${readinessStateClass}`}>{readinessState || "-"}</div>
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



