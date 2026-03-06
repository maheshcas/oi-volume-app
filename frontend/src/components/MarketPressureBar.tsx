type MarketPressureBarProps = {
  score: number;
  state: string;
};

export default function MarketPressureBar({ score, state }: MarketPressureBarProps) {
  const clamped = Math.max(0, Math.min(100, Number(score) || 0));
  const toneClass =
    clamped < 35
      ? "ia-pressure-sell"
      : clamped < 55
        ? "ia-pressure-balanced"
        : clamped < 75
          ? "ia-pressure-buy"
          : "ia-pressure-strong-buy";

  return (
    <div className="ia-pressure-wrap">
      <div className="ia-pressure-head">
        <span className="ia-kpi-label">Market Pressure</span>
        <span className={`ia-pressure-state ${toneClass}`}>{state}</span>
      </div>
      <div className="ia-pressure-track">
        <div className="ia-pressure-gradient" />
        <div className="ia-pressure-marker" style={{ left: `${clamped}%` }} />
      </div>
      <div className="ia-pressure-ends">
        <span>Sell</span>
        <span>{Math.round(clamped)}</span>
        <span>Buy</span>
      </div>
    </div>
  );
}

