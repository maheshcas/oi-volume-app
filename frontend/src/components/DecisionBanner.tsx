import {
  confidenceLabel,
  friendlyBlockingReason,
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
  trapPct?: number | null;
  winningEngine?: string;
  decisionConfidence?: number | null;
  supportTransitionBadge?: boolean;
  resistanceTransitionBadge?: boolean;
};

function formatDirectionLabel(direction: DecisionBannerProps["direction"]) {
  if (direction === "Neutral") return "Neutral bias";
  if (direction === "Conflict") return "Range conflict";
  return direction;
}

function stateLabel(action: "WAIT" | "CAUTION" | "READY"): string {
  if (action === "READY") return "Ready";
  if (action === "CAUTION") return "Caution";
  return "Wait";
}

function formatWinningEngineLabel(winningEngine?: string | null): string {
  const raw = String(winningEngine || "").trim();
  if (!raw) return "core decision logic";
  const normalized = raw.toLowerCase();
  if (normalized === "none" || normalized === "decision_flow" || normalized === "decision flow") {
    return "core decision logic";
  }
  return raw;
}

function resolveHeadline(
  action: DecisionBannerProps["action"],
  direction: DecisionBannerProps["direction"],
  explanation: string,
  blockingReason: string,
): string {
  const blocker = String(blockingReason || "").trim().toUpperCase();
  if (blocker && blocker !== "NONE") {
    const friendly = friendlyBlockingReason(blockingReason);
    if (action === "WAIT") return `${friendly} · waiting for a clean edge before committing`;
    if (action === "CAUTION") return `${friendly} · setup forming, confirmation pending`;
    return `${friendly} · conditions aligned for execution`;
  }
  const clean = (explanation || "").trim();
  if (clean) return clean;
  if (action === "READY") return "Conditions aligned for execution";
  if (action === "CAUTION") return "Setup forming, confirmation pending";
  return `${formatDirectionLabel(direction)} · waiting for a clean edge`;
}

function resolveUnlockHint(
  blockingReason: string,
  trapPct: number | null | undefined,
): string | null {
  const blocker = String(blockingReason || "").trim().toUpperCase();
  if (!blocker || blocker === "NONE") return null;
  if (blocker === "RANGE_CONFLICT")
    return "Spot reaches S or R edge — readiness holds above 60%";
  if (blocker === "TRAP_HIGH" && typeof trapPct === "number")
    return `Trap drops below 55% (now ${Math.round(trapPct)}%)`;
  if (blocker === "HIGH_TRAP_NO_BREACH_CAP")
    return "Trap easing + level breach confirmed";
  if (blocker === "LOW_READINESS")
    return "Readiness crosses 60% minimum threshold";
  if (blocker === "NO_BREAK_CONFIRMATION" || blocker === "NO_BREACH_CONFIRMATION")
    return "Breach confirmed with OI follow-through";
  if (blocker === "ABSORPTION_ACTIVE")
    return "Absorption resolves into directional move";
  if (blocker === "SUPPORT_TRANSITION")
    return "Support transition settles to a stable level";
  if (blocker === "RESISTANCE_TRANSITION")
    return "Resistance transition settles to a stable level";
  return "Structural conditions align";
}

function confidenceTone(raw: string): "low" | "mid" | "high" {
  const t = raw.toLowerCase();
  if (t.includes("high") || t.includes("strong")) return "high";
  if (t.includes("mid") || t.includes("moderate") || t.includes("medium"))
    return "mid";
  return "low";
}

function readinessTone(score: number): "below" | "near" | "above" {
  if (score >= 60) return "above";
  if (score >= 50) return "near";
  return "below";
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
  blockingReason = "NONE",
  trapPct = null,
  winningEngine = "",
  decisionConfidence = null,
  supportTransitionBadge = false,
  resistanceTransitionBadge = false,
}: DecisionBannerProps) {
  const stateWord = stateLabel(action);
  const phaseStr = String(sessionPhase || "").trim();
  const actionTone = action === "READY" ? "ready" : action === "CAUTION" ? "caution" : "wait";

  const readinessPct = Math.max(0, Math.min(100, Number(readinessScore) || 0));
  const confidencePct = Math.max(
    0,
    Math.min(100, Number(decisionConfidence) || 0),
  );

  const headline = resolveHeadline(action, direction, explanation, blockingReason);
  const unlockHint = resolveUnlockHint(blockingReason, trapPct);

  const biasLabel = bias || formatDirectionLabel(direction);
  const pressureLabel = pressureState.replace(/\s*Pressure$/i, "").trim() || pressureState;
  const regimeLabel = regime || "—";

  const rTone = readinessTone(readinessPct);
  const rStateText = readinessState
    ? readinessState
    : rTone === "above"
      ? "Above entry"
      : rTone === "near"
        ? "Near entry"
        : "Below entry";

  const cTone = confidenceTone(confidenceLabel(decisionConfidence));
  const cStateText =
    cTone === "high"
      ? "High"
      : cTone === "mid"
        ? "Medium"
        : "Low";
  const cSubText =
    blockingReason && blockingReason.toUpperCase() !== "NONE"
      ? friendlyBlockingReason(blockingReason).toLowerCase()
      : "—";

  const transitionLabel = supportTransitionBadge
    ? "Support Transition Active"
    : resistanceTransitionBadge
      ? "Resistance Transition Active"
      : null;

  const engineLabel = formatWinningEngineLabel(winningEngine);
  const capLabel =
    blockingReason && blockingReason.toUpperCase() !== "NONE"
      ? String(blockingReason).replace(/_/g, " ").toLowerCase()
      : null;

  return (
    <div className={`ia-card ia-decision-banner-v3 ia-decision-banner-v3-${actionTone}`}>
      <div className="db-v3-header">
        <div className="db-v3-state-group">
          <span className="db-v3-eyebrow">Trade Signal</span>
          <div className="db-v3-state">
            <span className="db-v3-state-dot" />
            <span className="db-v3-state-label">{stateWord}</span>
            {phaseStr ? (
              <span className="db-v3-state-sub">· {phaseStr.toLowerCase()}</span>
            ) : null}
          </div>
        </div>

        <div className="db-v3-meta">
          <span>{biasLabel}</span>
          <span className="db-v3-meta-sep">·</span>
          <span>{pressureLabel}</span>
          <span className="db-v3-meta-sep">·</span>
          <span>{regimeLabel}</span>
        </div>
      </div>

      <div className="db-v3-headline">{headline}</div>

      {transitionLabel ? (
        <div className="db-v3-transition">{transitionLabel}</div>
      ) : null}

      <div className="db-v3-body">
        <div className="db-v3-cell">
          <div className="db-v3-cell-head">
            <span className="db-v3-cell-key">Trade Readiness</span>
            <span className={`db-v3-cell-pct db-v3-cell-pct-${rTone}`}>
              {Math.round(readinessPct)}%
            </span>
          </div>
          <div className="db-v3-bar" aria-hidden="true">
            <div
              className={`db-v3-bar-fill db-v3-bar-fill-${rTone}`}
              style={{ width: `${readinessPct}%` }}
            />
            <div className="db-v3-bar-tick" style={{ left: "60%" }} />
          </div>
          <div className="db-v3-cell-foot">
            <span
              className={`db-v3-cell-state db-v3-cell-state-${rTone}`}
            >
              {rStateText}
            </span>
            <span className="db-v3-cell-threshold">min 60%</span>
          </div>
          {readinessExplainability ? (
            <div className="db-v3-cell-note">{readinessExplainability}</div>
          ) : null}
        </div>

        <div className="db-v3-cell">
          <div className="db-v3-cell-head">
            <span className="db-v3-cell-key">Decision Confidence</span>
            <span className={`db-v3-cell-pct db-v3-cell-pct-${cTone}`}>
              {Math.round(confidencePct)}%
            </span>
          </div>
          <div className="db-v3-bar" aria-hidden="true">
            <div
              className={`db-v3-bar-fill db-v3-bar-fill-${cTone}`}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <div className="db-v3-cell-foot">
            <span
              className={`db-v3-cell-state db-v3-cell-state-${cTone}`}
            >
              {cStateText}
            </span>
            <span className="db-v3-cell-threshold">{cSubText}</span>
          </div>
        </div>

        {unlockHint ? (
          <div className="db-v3-unlock">
            <div className="db-v3-unlock-label">Unlock when</div>
            <div className="db-v3-unlock-body">{unlockHint}</div>
          </div>
        ) : (
          <div className="db-v3-unlock db-v3-unlock-clear">
            <div className="db-v3-unlock-label">Status</div>
            <div className="db-v3-unlock-body">
              {action === "READY"
                ? "All gates cleared · execute with plan"
                : "No active blocker · monitoring for signal"}
            </div>
          </div>
        )}
      </div>

      <div className="db-v3-footer">
        <div className="db-v3-footer-left">
          <span>Engine: {engineLabel}</span>
          {capLabel ? (
            <>
              <span className="db-v3-footer-sep">·</span>
              <span>Cap: {capLabel}</span>
            </>
          ) : null}
        </div>
        <div className="db-v3-footer-right">
          <span>
            State: <span className="db-v3-footer-state">{rStateText}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
