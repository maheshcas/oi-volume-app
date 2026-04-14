type MarketBannerProps = {
  indexName: string;
  spot: string;
  spotDelta?: string;
  fromOpenDelta?: string;
  pctChange: string;
  volatilityState: "Expanding" | "Contracting" | "Stable";
  regime?: string;
  regimeExplanation?: string;
  supportLevel?: number | null;
  resistanceLevel?: number | null;
  updatedAt: string;
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
  expiryMode?: boolean;
  phase?: string;
  projection?: string;
  showProjection?: boolean;
  alerts?: Array<{
    message: string;
    type: "primary" | "counter" | "warning" | string;
    source?: string;
    tier?: string;
  }>;
};

const alertColors: Record<string, string> = {
  primary: "ia-alert-bull",
  counter: "ia-alert-bear",
  warning: "ia-alert-warn",
};

function splitSpotParts(value: string) {
  const text = String(value ?? "").trim();
  if (!text || text === "-") {
    return { whole: "-", decimal: "" };
  }
  const numeric = Number(text.replace(/,/g, ""));
  if (Number.isFinite(numeric)) {
    return { whole: Math.round(numeric).toLocaleString("en-IN"), decimal: "" };
  }
  const [whole] = text.split(".");
  return { whole, decimal: "" };
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
  const spotNum = Number(String(props.spot || "").replace(/,/g, ""));
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

  const liveTitle =
    props.liveStatus === "live"
      ? "Live — data updated within seconds"
      : props.liveStatus === "stale"
        ? "Stale — last update >30s ago, use with caution"
        : props.liveStatus === "delayed"
          ? "Delayed — data is 1+ min old, do not trade on this"
          : props.liveStatus === "blocked"
            ? "Blocked — data feed unavailable"
            : "Checking — waiting for data connection";

  const pctDown = isNegativeDelta(props.pctChange) || isNegativeDelta(props.spotDelta);
  const openDeltaDown = isNegativeDelta(props.fromOpenDelta);
  const projectionTone = props.projection?.toLowerCase().includes("down")
    ? "ia-text-bear"
    : props.projection?.toLowerCase().includes("up")
      ? "ia-text-bull"
      : "";
  const regimeLabel = props.regime ?? (props.volatilityState === "Stable" ? "Range Day" : "Trend Day");
  const projectionLabel = props.projection ?? "No breakout signal";
  const bandLabel =
    typeof props.supportLevel === "number" && Number.isFinite(props.supportLevel) &&
    typeof props.resistanceLevel === "number" && Number.isFinite(props.resistanceLevel)
      ? `${props.supportLevel.toLocaleString("en-IN")} – ${props.resistanceLevel.toLocaleString("en-IN")}`
      : "levels unavailable";
  const stanceLabel = regimeLabel.toLowerCase().includes("range") ? "Range bound" : regimeLabel;
  const breakoutLabel = /breakout/i.test(projectionLabel) ? projectionLabel : "No breakout signal";
  const distToS =
    Number.isFinite(spotNum) && typeof props.supportLevel === "number"
      ? Math.abs(spotNum - props.supportLevel)
      : null;
  const distToR =
    Number.isFinite(spotNum) && typeof props.resistanceLevel === "number"
      ? Math.abs(props.resistanceLevel - spotNum)
      : null;
  const nearestLevel =
    distToS !== null && distToR !== null && typeof props.supportLevel === "number" && typeof props.resistanceLevel === "number"
      ? distToS < distToR
        ? `support ${props.supportLevel.toLocaleString("en-IN")}`
        : `resistance ${props.resistanceLevel.toLocaleString("en-IN")}`
      : "key levels";
  const summaryFromLegacy = String(props.regimeExplanation || "").replace(
    "Needs 3x Balanced Structure to advance",
    `Range bound · no breakout signal · watch ${nearestLevel}`,
  );
  const summaryLine = summaryFromLegacy || `${stanceLabel} · ${bandLabel} · ${breakoutLabel}`;

  return (
    <div className="ia-status-bar">
      <div className="ia-banner-row ia-banner-row-primary">
        <span className="ia-inline-pill">{props.indexName}</span>
        <span className={`ia-live-badge ${liveTone}`} title={liveTitle}>
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
        <span className="ia-banner-group ia-banner-group-compact">
          <span className="ia-banner-label">From Open</span>
          {props.fromOpenDelta
            ? <span className={openDeltaDown ? "ia-text-bear" : "ia-text-bull"}>{props.fromOpenDelta}</span>
            : <span>-</span>}
        </span>
        <span className="ia-banner-group ia-banner-group-compact">
          <span className="ia-banner-label">Updated</span>
          <span>{props.updatedAt}</span>
        </span>
      </div>

      {props.alerts && props.alerts.length > 0 ? (
        <div className="ia-alert-ticker">
          <span className="ia-alert-ticker-label">LIVE</span>
          <div className="ia-alert-ticker-track">
            {props.alerts.map((a, i) => (
              <span
                key={`${a.message}-${i}`}
                className={`ia-alert-chip ${alertColors[a.type] ?? "ia-alert-warn"}`}
              >
                {a.message}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="ia-banner-row ia-banner-row-secondary">
        <span className="ia-pill ia-pill-status">
          {regimeLabel}
        </span>
        {props.showProjection === false ? null : (
          <span className={`ia-pill ia-pill-status ${projectionTone ? "ia-pill-status-emphasis" : ""}`}>
            {projectionLabel}
          </span>
        )}
      </div>
      <div className="ia-banner-regime-note">{summaryLine}</div>
    </div>
  );
}
