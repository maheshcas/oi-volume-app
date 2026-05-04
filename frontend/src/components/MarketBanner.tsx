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
  scheduleLabel?: string;
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
  chainPcr?: number | null;
  chainPcrBias?: string | null;
  chainPcrTrend?: string | null;
};

function splitSpotParts(value: string) {
  const text = String(value ?? "").trim();
  if (!text || text === "-") return { whole: "-", decimal: "" };
  const numeric = Number(text.replace(/,/g, ""));
  if (Number.isFinite(numeric))
    return { whole: Math.round(numeric).toLocaleString("en-IN"), decimal: "" };
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

function trimTimestamp(ts: string): string {
  const t = String(ts || "").trim();
  if (!t) return "";
  const m = t.match(/(\d{1,2}):(\d{2}):(\d{2})/);
  if (m) return `${m[1]}:${m[2]}:${m[3]}`;
  const m2 = t.match(/(\d{1,2}):(\d{2})/);
  if (m2) return `${m2[1]}:${m2[2]}`;
  return t;
}

function cleanPct(value?: string): string {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.replace(/^[▲▼↑↓+\-\s]+/, "").trim();
}

function cleanAbs(value?: string): string {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.replace(/^[▲▼↑↓\s]+/, "").trim();
}

type AlertItem = NonNullable<MarketBannerProps["alerts"]>[number];

function alertSeverity(a: AlertItem): "high" | "watch" | "info" {
  const tier = String(a.tier || "").toLowerCase();
  if (tier === "high" || tier === "critical") return "high";
  if (tier === "watch" || tier === "warn" || tier === "warning") return "watch";
  const type = String(a.type || "").toLowerCase();
  if (type === "warning") return "watch";
  if (type === "counter") return "watch";
  return "info";
}

function alertTone(a: AlertItem): "bull" | "bear" | "warn" {
  const type = String(a.type || "").toLowerCase();
  if (type === "primary") return "bull";
  if (type === "counter") return "bear";
  return "warn";
}

export default function MarketBanner(props: MarketBannerProps) {
  const spotParts = splitSpotParts(props.spot);
  const spotNum = Number(String(props.spot || "").replace(/,/g, ""));

  const liveTone =
    props.liveStatus === "live"
      ? "ok"
      : props.liveStatus === "stale"
        ? "stale"
        : props.liveStatus === "delayed" || props.liveStatus === "blocked"
          ? "delayed"
          : "checking";

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

  const regimeLabel = props.regime ?? (props.volatilityState === "Stable" ? "Range Day" : "Trend Day");
  const projectionLabel = props.projection ?? "No breakout signal";
  const projectionIsBreakout = /breakout/i.test(projectionLabel);
  const projectionTone = projectionIsBreakout
    ? props.projection?.toLowerCase().includes("down")
      ? "bear"
      : "bull"
    : "neutral";

  const bandLabel =
    typeof props.supportLevel === "number" && Number.isFinite(props.supportLevel) &&
    typeof props.resistanceLevel === "number" && Number.isFinite(props.resistanceLevel)
      ? `${props.supportLevel.toLocaleString("en-IN")} – ${props.resistanceLevel.toLocaleString("en-IN")}`
      : null;

  const distToS =
    Number.isFinite(spotNum) && typeof props.supportLevel === "number"
      ? Math.abs(spotNum - props.supportLevel)
      : null;
  const distToR =
    Number.isFinite(spotNum) && typeof props.resistanceLevel === "number"
      ? Math.abs(props.resistanceLevel - spotNum)
      : null;

  const nearestLabel =
    distToS !== null && distToR !== null &&
    typeof props.supportLevel === "number" &&
    typeof props.resistanceLevel === "number"
      ? distToS < distToR
        ? `support ${props.supportLevel.toLocaleString("en-IN")}`
        : `resistance ${props.resistanceLevel.toLocaleString("en-IN")}`
      : null;

  const stanceWord = regimeLabel.toLowerCase().includes("range")
    ? "Spot holding inside range"
    : regimeLabel.toLowerCase().includes("trend")
      ? "Spot trending"
      : "Spot active";

  const summaryPrefix = stanceWord;
  const summaryAction = nearestLabel ? `watch ${nearestLabel}` : null;

  const absChange = cleanAbs(props.spotDelta);
  const pctDisplay = cleanPct(props.pctChange);

  const displayTimestamp = trimTimestamp(props.updatedAt);

  const sortedAlerts = (props.alerts ?? []).slice().sort((a, b) => {
    const order = { high: 0, watch: 1, info: 2 } as const;
    return order[alertSeverity(a)] - order[alertSeverity(b)];
  });

  return (
    <div className="mb-v2">
      <div className="mb-v2-hero">
        <div className="mb-v2-identity">
          <span className="mb-v2-eyebrow">{props.indexName}</span>
          <div className={`mb-v2-live mb-v2-live-${liveTone}`} title={liveTitle}>
            <span className="mb-v2-live-dot" />
            <span className="mb-v2-live-label">
              {liveLabel}
              {displayTimestamp && liveTone === "ok" ? (
                <span className="mb-v2-live-time"> · {displayTimestamp}</span>
              ) : null}
            </span>
          </div>
          {props.scheduleLabel && liveTone === "ok" ? null : props.scheduleLabel ? (
            <span className="mb-v2-schedule">{props.scheduleLabel}</span>
          ) : null}
        </div>

        <div className="mb-v2-price">
          <span className="mb-v2-price-whole">{spotParts.whole}</span>
          <div className={`mb-v2-price-change mb-v2-price-change-${pctDown ? "down" : "up"}`}>
            {absChange ? (
              <span className="mb-v2-price-abs">
                {pctDown ? "▼" : "▲"} {absChange}
              </span>
            ) : null}
            {pctDisplay ? (
              <span className="mb-v2-price-pct">{pctDisplay}</span>
            ) : null}
          </div>
        </div>

        <div className="mb-v2-secondary">
          {props.fromOpenDelta ? (
            <div className="mb-v2-sec-item">
              <span className="mb-v2-sec-key">From Open</span>
              <span className={`mb-v2-sec-val ${openDeltaDown ? "mb-v2-sec-val-down" : "mb-v2-sec-val-up"}`}>
                {props.fromOpenDelta}
              </span>
            </div>
          ) : null}
          {typeof props.chainPcr === "number" ? (
            <div className="mb-v2-sec-item">
              <span className="mb-v2-sec-key">PCR</span>
              <span className={`mb-v2-sec-val mb-v2-pcr-${(props.chainPcrBias ?? "neutral").toLowerCase()}`}>
                {props.chainPcr.toFixed(2)}
                {props.chainPcrTrend && props.chainPcrTrend !== "stable" ? (
                  <span className="mb-v2-pcr-trend">
                    {" "}{props.chainPcrTrend === "rising" ? "↑" : "↓"}
                  </span>
                ) : null}
              </span>
            </div>
          ) : null}
          {bandLabel ? (
            <div className="mb-v2-sec-item">
              <span className="mb-v2-sec-key">Band</span>
              <span className="mb-v2-sec-val">{bandLabel}</span>
            </div>
          ) : null}
          {liveTone !== "ok" && displayTimestamp ? (
            <div className="mb-v2-sec-item">
              <span className="mb-v2-sec-key">Updated</span>
              <span className="mb-v2-sec-val mb-v2-sec-val-stale">{displayTimestamp}</span>
            </div>
          ) : null}
        </div>

        <div className="mb-v2-classification">
          <span className="mb-v2-pill mb-v2-pill-regime">{regimeLabel}</span>
          {props.showProjection === false ? null : (
            <span className={`mb-v2-pill mb-v2-pill-${projectionTone}`}>
              {projectionLabel}
            </span>
          )}
        </div>
      </div>

      {(summaryPrefix || summaryAction) ? (
        <div className="mb-v2-summary">
          {summaryPrefix ? <span>{summaryPrefix}</span> : null}
          {summaryAction ? (
            <>
              <span className="mb-v2-summary-sep"> · </span>
              <span className="mb-v2-summary-action">{summaryAction}</span>
            </>
          ) : null}
        </div>
      ) : null}

      {sortedAlerts.length > 0 ? (
        <div className="mb-v2-alerts">
          <div className="mb-v2-alerts-head">
            <span className="mb-v2-alerts-label">Alerts</span>
            <span className="mb-v2-alerts-count">{sortedAlerts.length}</span>
          </div>
          <div className="mb-v2-alerts-track">
            {sortedAlerts.map((a, i) => {
              const sev = alertSeverity(a);
              const tone = alertTone(a);
              return (
                <span
                  key={`${a.message}-${i}`}
                  className={`mb-v2-alert-chip mb-v2-alert-chip-${tone}`}
                >
                  <span className={`mb-v2-alert-dot mb-v2-alert-dot-${sev}`} />
                  {a.message}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
