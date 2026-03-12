type TradeReadinessIndicatorProps = {
  state: string;
  score: number;
};

export default function TradeReadinessIndicator({
  state,
  score,
}: TradeReadinessIndicatorProps) {
  const normalizedState = String(state || "Low");
  const toneClass =
    normalizedState === "High"
      ? "ia-readiness-ready"
      : normalizedState === "Moderate"
        ? "ia-readiness-caution"
        : "ia-readiness-wait";

  return (
    <div className="ia-readiness-wrap ia-emphasis-high">
      <span className="ia-kpi-label">Trade Readiness</span>
      <span className={`ia-readiness-pill ${toneClass}`}>
        {Math.round(Math.max(0, Math.min(100, score)))}% ? {normalizedState}
      </span>
    </div>
  );
}
