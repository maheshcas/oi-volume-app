type MarketBannerProps = {
  indexName: string;
  spot: string;
  spotDelta?: string;
  fromOpenDelta?: string;
  pctChange: string;
  volatilityState: "Expanding" | "Contracting" | "Stable";
  regime?: string;
  regimeExplanation?: string;
  updatedAt: string;
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
  expiryMode?: boolean;
  phase?: string;
  projection?: string;
  showProjection?: boolean;
  dayTrend?: string;
  longTrend?: string;
};

function splitSpotParts(value: string) {
  const text = String(value ?? "").trim();
  if (!text || text === "-") {
    return { whole: "-", decimal: "" };
  }
  const [whole, decimal] = text.split(".");
  return { whole, decimal: decimal ? `.${decimal}` : "" };
}

function toneForTrend(label?: string) {
  const text = String(label ?? "").toLowerCase();
  if (text.includes("bull") || text.includes("up")) return "ia-pill-trend-bull";
  if (text.includes("bear") || text.includes("down")) return "ia-pill-trend-bear";
  return "ia-pill-trend-neutral";
}

function isNegativeDelta(value?: string) {
  const text = String(value ?? "").trim();
  if (!text) return false;
  return (
    text.startsWith("-") ||
    text.startsWith("▼") ||
    text.startsWith("↓") ||
    text.includes(" -") ||
    text.includes("▼") ||
    text.includes("↓")
  );
}

export default function MarketBanner(props: MarketBannerProps) {
  const spotParts = splitSpotParts(props.spot);
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

  const pctDown = isNegativeDelta(props.pctChange) || isNegativeDelta(props.spotDelta);
  const openDeltaDown = isNegativeDelta(props.fromOpenDelta);
  const projectionTone = props.projection?.toLowerCase().includes("down")
    ? "ia-text-bear"
    : props.projection?.toLowerCase().includes("up")
      ? "ia-text-bull"
      : "";
  const phaseText = (props.phase || "").toLowerCase();
  const phaseLabel = phaseText.includes("opening")
    ? "Opening Drive"
    : phaseText.includes("structure")
      ? "Structure Formation"
      : phaseText.includes("compression")
        ? "Compression Phase"
        : phaseText.includes("position")
          ? "Position Build Phase"
          : phaseText.includes("expansion") || phaseText.includes("power") || phaseText.includes("closing")
            ? "Expansion Window"
            : "Transition";
  const phaseTone = phaseText.includes("opening")
    ? "ia-phase-opening"
    : phaseText.includes("structure")
      ? "ia-phase-transition"
      : phaseText.includes("compression")
        ? "ia-phase-midday"
        : phaseText.includes("position")
          ? "ia-phase-transition"
          : phaseText.includes("expansion") || phaseText.includes("power") || phaseText.includes("closing")
            ? "ia-phase-power"
            : "ia-phase-transition";

  return (
    <div className="ia-status-bar">
      <div className="ia-banner-row ia-banner-row-primary">
        <span className="ia-inline-pill">{props.indexName}</span>
        <span className={`ia-live-badge ${liveTone}`}>
          <span className={`ia-live-dot ${liveTone}`} />
          {liveLabel}
        </span>
      </div>

      <div className="ia-banner-spot-row">
        <span className="ia-spot-strong">
          <span className="ia-spot-int">{spotParts.whole}</span>
          {spotParts.decimal ? <span className="ia-spot-dec">{spotParts.decimal}</span> : null}
        </span>
        <span className={`ia-spot-change-badge ${pctDown ? "ia-spot-change-badge-down" : "ia-spot-change-badge-up"}`}>
          {props.spotDelta ? `${props.spotDelta} ${props.pctChange}` : props.pctChange}
        </span>
      </div>

      <div className="ia-banner-row ia-banner-row-spot-meta">
        <span className="ia-banner-group ia-banner-group-compact">
          <span className="ia-banner-label">Vs Prev Close</span>
          {props.spotDelta ? <span className={pctDown ? "ia-text-bear" : "ia-text-bull"}>{props.spotDelta}</span> : <span>-</span>}
        </span>
        {props.fromOpenDelta ? (
          <span className="ia-banner-group ia-banner-group-compact">
            <span className="ia-banner-label">From Open</span>
            <span className={openDeltaDown ? "ia-text-bear" : "ia-text-bull"}>{props.fromOpenDelta}</span>
          </span>
        ) : null}
        <span className="ia-banner-group ia-banner-group-compact">
          <span className="ia-banner-label">Updated</span>
          <span>{props.updatedAt}</span>
        </span>
      </div>

      <div className="ia-banner-row ia-banner-row-secondary">
        <span className="ia-pill ia-pill-status">
          Regime: {props.regime ?? (props.volatilityState === "Stable" ? "Range Day" : "Trend Day")}
        </span>
        {props.expiryMode ? <span className="ia-pill ia-pill-active">Expiry Mode</span> : null}
        {props.showProjection === false ? null : (
          <span className={`ia-pill ia-pill-status ${projectionTone ? "ia-pill-status-emphasis" : ""}`}>
            Projection: {props.projection ?? "Range"}
          </span>
        )}
        <span className={`ia-pill ia-pill-trend ${toneForTrend(props.dayTrend)}`}>
          Day: {props.dayTrend ?? "-"}
        </span>
        <span className={`ia-pill ia-pill-trend ${toneForTrend(props.longTrend)}`}>
          Long: {props.longTrend ?? "-"}
        </span>
        <span className={`ia-pill ia-pill-active ${phaseTone}`}>Phase: {phaseLabel}</span>
      </div>
      {props.regimeExplanation ? (
        <div className="ia-banner-regime-note">{props.regimeExplanation}</div>
      ) : null}
    </div>
  );
}
