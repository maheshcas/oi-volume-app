type TradeReadinessIndicatorProps = {
  state: "WAIT" | "CAUTION" | "READY";
  score: number;
};

export default function TradeReadinessIndicator({
  state,
  score,
}: TradeReadinessIndicatorProps) {
  const toneClass =
    state === "READY"
      ? "ia-readiness-ready"
      : state === "CAUTION"
        ? "ia-readiness-caution"
        : "ia-readiness-wait";

  return (
    <div className="ia-readiness-wrap ia-emphasis-high">
      <span className="ia-kpi-label">Trade Readiness</span>
      <span className={`ia-readiness-pill ${toneClass}`}>
        {state} ({Math.round(Math.max(0, Math.min(100, score)))}%)
      </span>
    </div>
  );
}
