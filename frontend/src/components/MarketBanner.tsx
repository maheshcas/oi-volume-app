type MarketBannerProps = {
  indexName: string;
  spot: string;
  spotDelta?: string;
  fromOpenDelta?: string;
  pctChange: string;
  volatilityState: "Expanding" | "Contracting" | "Stable";
  regime?: string;
  updatedAt: string;
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
  expiryMode?: boolean;
  phase?: string;
  projection?: string;
  showProjection?: boolean;
  trend?: "Bullish" | "Bearish" | "Neutral";
};

export default function MarketBanner(props: MarketBannerProps) {
  const liveTone =
    props.liveStatus === "live"
      ? "ia-live-ok"
      : props.liveStatus === "stale"
        ? "ia-live-stale"
        : props.liveStatus === "delayed" || props.liveStatus === "blocked"
          ? "ia-live-delayed"
          : "ia-live-checking";

  const liveLabel =
    props.liveStatus === "live"
      ? "LIVE"
      : props.liveStatus === "stale"
        ? "STALE"
        : props.liveStatus === "delayed"
          ? "DELAYED"
          : props.liveStatus === "blocked"
            ? "BLOCKED"
            : "CHECKING";

  const pctDown = props.pctChange.trim().startsWith("-");
  const openDeltaDown = String(props.fromOpenDelta ?? "").trim().startsWith("-") || String(props.fromOpenDelta ?? "").includes("▼");
  const trendTone =
    props.trend === "Bullish" ? "ia-text-bull" : props.trend === "Bearish" ? "ia-text-bear" : "";
  const projectionTone =
    props.projection?.toLowerCase().includes("down")
      ? "ia-text-bear"
      : props.projection?.toLowerCase().includes("up")
        ? "ia-text-bull"
        : "";
  const phaseText = (props.phase || "").toLowerCase();
  const phaseLabel = phaseText.includes("opening")
    ? "Opening Drive"
    : phaseText.includes("midday")
      ? "Midday Compression"
      : phaseText.includes("closing")
        ? "Power Hour"
        : "Transition";
  const phaseTone = phaseText.includes("opening")
    ? "ia-phase-opening"
    : phaseText.includes("midday")
      ? "ia-phase-midday"
      : phaseText.includes("closing")
        ? "ia-phase-power"
        : "ia-phase-transition";

  return (
    <div className="ia-status-bar">
      <div className="ia-banner-row ia-banner-row-primary">
        <span className="ia-inline-pill">{props.indexName}</span>
        <span className="ia-banner-group">
          <span className="ia-banner-label">Spot</span>
          <span className="ia-spot-strong">{props.spot}</span>
        </span>
        <span className="ia-banner-group">
          <span className="ia-banner-label">Vs Prev Close</span>
          {props.spotDelta ? <span className={pctDown ? "ia-text-bear" : "ia-text-bull"}>{props.spotDelta}</span> : <span>-</span>}
        </span>
        <span className="ia-banner-group">
          <span className="ia-banner-label">Change</span>
          <span className={pctDown ? "ia-text-bear" : "ia-text-bull"}>{props.pctChange}</span>
        </span>
        {props.fromOpenDelta ? (
          <span className="ia-banner-group">
            <span className="ia-banner-label">From Open</span>
            <span className={openDeltaDown ? "ia-text-bear" : "ia-text-bull"}>{props.fromOpenDelta}</span>
          </span>
        ) : null}
        <span className="ia-banner-group">
          <span className="ia-banner-label">Updated</span>
          <span>{props.updatedAt}</span>
        </span>
        <span className={`ia-live-badge ${liveTone}`}>
          <span className={`ia-live-dot ${liveTone}`} />
          {liveLabel}
        </span>
      </div>

      <div className="ia-banner-row ia-banner-row-secondary">
        <span className="ia-banner-group">
          <span className="ia-banner-label">Regime</span>
          <span>{props.regime ?? (props.volatilityState === "Stable" ? "Range Day" : "Trend Day")}</span>
        </span>
        {props.expiryMode ? (
          <span className="ia-inline-pill ia-chip-expiry">Expiry Mode</span>
        ) : null}
        {props.showProjection === false ? null : (
          <span className="ia-banner-group">
            <span className="ia-banner-label">Projection</span>
            <span className={projectionTone}>{props.projection ?? "Range"}</span>
          </span>
        )}
        <span className="ia-banner-group">
          <span className="ia-banner-label">Trend</span>
          <span className={trendTone}>{props.trend ?? "Neutral"}</span>
        </span>
        <span className={`ia-inline-pill ${phaseTone}`}>Phase: {phaseLabel}</span>
      </div>
    </div>
  );
}
