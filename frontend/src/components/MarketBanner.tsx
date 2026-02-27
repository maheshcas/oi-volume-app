type MarketBannerProps = {
  indexName: string;
  spot: string;
  spotChange: string;
  pctChange: string;
  expiry: string;
  pcr: string;
  maxPain: string;
  regime: string;
  projection: string;
  trend: string;
  phase: string;
  updatedAt: string;
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
};

export default function MarketBanner(props: MarketBannerProps) {
  const liveTone =
    props.liveStatus === "live"
      ? "ia-live-ok"
      : props.liveStatus === "stale"
        ? "ia-live-stale"
        : props.liveStatus === "delayed"
          ? "ia-live-delayed"
      : props.liveStatus === "blocked"
        ? "ia-live-blocked"
        : "ia-live-checking";
  const liveLabel =
    props.liveStatus === "delayed"
      ? "Delayed"
      : props.liveStatus === "stale"
        ? "Stale"
        : props.liveStatus === "blocked"
          ? "Blocked"
        : props.liveStatus === "checking"
          ? "Checking"
          : "Live";
  const spotTone = props.spotChange.trim().startsWith("▼") ? "ia-chip-down" : "ia-chip-up";
  const projectionTone =
    props.projection.toLowerCase().includes("down")
      ? "ia-bias-bear"
      : props.projection.toLowerCase().includes("up")
        ? "ia-bias-bull"
        : "ia-bias-neutral";
  const trendTone =
    props.trend.toLowerCase().includes("bear")
      ? "ia-bias-bear"
      : props.trend.toLowerCase().includes("bull")
        ? "ia-bias-bull"
        : "ia-bias-neutral";

  return (
    <div className="ia-status-bar">
      <div className="ia-banner-row ia-banner-row-primary">
        <span className="ia-banner-title">{props.indexName}</span>
        <span className="ia-sep">|</span>
        <span>
          Spot: <span className="ia-spot-strong">{props.spot}</span>
        </span>
        <span className={`ia-chip ${spotTone}`}>{props.spotChange}</span>
        <span className="ia-sep">|</span>
        <span>
          % Change: <span className={spotTone === "ia-chip-down" ? "ia-text-bear" : "ia-text-bull"}>{props.pctChange}</span>
        </span>
        <span className="ia-sep">|</span>
        <span>Exp: {props.expiry}</span>
        <span className="ia-sep">|</span>
        <span>PCR: {props.pcr}</span>
        <span className="ia-sep">|</span>
        <span>Max Pain: {props.maxPain}</span>
      </div>
      <div className="ia-banner-row ia-banner-row-secondary">
        <span>Regime: {props.regime}</span>
        <span className="ia-sep">|</span>
        <span>
          Projection: <span className={`ia-inline-pill ${projectionTone}`}>{props.projection}</span>
        </span>
        <span className="ia-sep">|</span>
        <span>
          Trend: <span className={`ia-inline-pill ${trendTone}`}>{props.trend}</span>
        </span>
        <span className="ia-sep">|</span>
        <span>Phase: {props.phase}</span>
        <span className="ia-sep">|</span>
        <span>Updated: {props.updatedAt}</span>
        <span className={`ia-live-badge ${liveTone}`}>
          <span className={`ia-live-dot ${liveTone}`} />
          {liveLabel}
        </span>
      </div>
    </div>
  );
}
