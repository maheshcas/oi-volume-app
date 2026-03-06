type MarketStructureScoreBadgeProps = {
  score: number | null | undefined;
  state: string | null | undefined;
};

export default function MarketStructureScoreBadge({
  score,
  state,
}: MarketStructureScoreBadgeProps) {
  const safeScore = Number.isFinite(Number(score)) ? Math.round(Number(score)) : null;
  const label = state && state.trim() ? state : "N/A";
  const toneClass =
    safeScore === null
      ? "ia-mss-neutral"
      : safeScore > 80
        ? "ia-mss-strong"
        : safeScore > 65
          ? "ia-mss-developing"
          : safeScore >= 50
            ? "ia-mss-balanced"
            : "ia-mss-risk";
  return (
    <span className={`ia-mss-badge ${toneClass}`} title="Market Structure Score">
      Market Structure Score: {safeScore !== null ? safeScore : "-"} | Status: {label}
    </span>
  );
}
