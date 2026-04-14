export type DecisionBlockingReason =
  | "TRAP_HIGH"
  | "ABSORPTION_ACTIVE"
  | "NO_BREAK_CONFIRMATION"
  | "LONG_BIAS_GUARD"
  | "LOW_READINESS"
  | "RANGE_CONFLICT"
  | "SUPPORT_TRANSITION"
  | "RESISTANCE_TRANSITION"
  | "NONE"
  | string;

export type WinningEngine =
  | "trap_engine"
  | "material_breach_engine"
  | "absorption_detector"
  | "readiness_gate"
  | "promotion_guard"
  | "sr_transition_guard"
  | "none"
  | string;

export type SignalHistoryItem = {
  timestamp?: string;
  trade_action?: string;
  resolved_reason?: string;
  blocking_reason?: string;
  winning_engine?: string;
  decision_confidence?: number;
};

export function friendlyBlockingReason(reason: DecisionBlockingReason): string {
  switch (reason) {
    case "TRAP_HIGH":
      return "Fake breakout risk";
    case "ABSORPTION_ACTIVE":
      return "Support absorption active";
    case "NO_BREAK_CONFIRMATION":
      return "No breakout confirmation";
    case "NO_BREACH_CONFIRMATION":
      return "No breakout confirmation";
    case "LONG_BIAS_GUARD":
      return "Promotion guard active";
    case "LOW_READINESS":
      return "Readiness below threshold";
    case "RANGE_CONFLICT":
      return "Range conflict";
    case "SUPPORT_TRANSITION":
      return "Support transition active";
    case "RESISTANCE_TRANSITION":
      return "Resistance transition active";
    default:
      return "No active blocker";
  }
}

export function friendlyWinningEngine(engine: WinningEngine): string {
  const normalized = String(engine ?? "").trim().toLowerCase();
  if (!normalized || normalized === "none" || normalized === "decision_flow" || normalized === "decision flow") {
    return "Driven by core decision logic";
  }

  switch (engine) {
    case "trap_engine":
      return "Driven by Trap Engine";
    case "material_breach_engine":
      return "Driven by Breach Engine";
    case "absorption_detector":
      return "Driven by Absorption";
    case "readiness_gate":
      return "Driven by Readiness Gate";
    case "promotion_guard":
      return "Driven by Promotion Guard";
    case "sr_transition_guard":
      return "Driven by Level Transition";
    default:
      return `Driven by ${String(engine).trim()}`;
  }
}

export function confidenceLabel(value: number | null | undefined): "High" | "Moderate" | "Low" {
  const score = typeof value === "number" && Number.isFinite(value) ? value : 0;
  if (score >= 75) return "High";
  if (score >= 55) return "Moderate";
  return "Low";
}

export function formatDecisionTime(timestamp?: string): string {
  if (!timestamp) return "--:--";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    const match = timestamp.match(/(\d{2}):(\d{2})/);
    return match ? `${match[1]}:${match[2]}` : "--:--";
  }
  return parsed.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
}
