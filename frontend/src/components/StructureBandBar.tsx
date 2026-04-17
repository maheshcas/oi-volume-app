import { useMemo } from "react";

type StrikePoint = {
  strike: number;
  oi_ce: number;
  oi_pe: number;
  tag?: "pe_wall" | "ce_wall" | "magnet" | "maxpain" | null;
};

type ChainRow = {
  strike: number;
  ce?: { delta?: number; ltp?: number };
  pe?: { delta?: number; ltp?: number };
};

type StructureBandBarProps = {
  spot: number;
  support: number;
  resistance: number;
  previousResistance?: number | null;
  peWall?: number | null;
  ceWall?: number | null;
  magnet?: number | null;
  magnetCharacter?: string | null;
  magnetPullDirection?: string | null;
  prevMagnetDirection?: string | null;
  maxPain?: number | null;
  strikeGap?: number;
  strikes?: StrikePoint[] | null;
  chainGreeks?: ChainRow[] | null;
  /** When true, hides the top stats row and zone-chip row (used when parent already shows them) */
  embedded?: boolean;
};

const fmt = (value?: number | null) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-IN", { maximumFractionDigits: 0 })
    : "-";

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

export default function StructureBandBar({
  spot,
  support,
  resistance,
  previousResistance,
  peWall,
  ceWall,
  magnet,
  magnetCharacter,
  magnetPullDirection,
  prevMagnetDirection,
  maxPain,
  strikeGap = 50,
  strikes,
  chainGreeks,
  embedded = false,
}: StructureBandBarProps) {
  const bandWidth = resistance - support;
  if (!Number.isFinite(bandWidth) || bandWidth <= 0) return null;

  const distToS = Math.round(spot - support);
  const distToR = Math.round(resistance - spot);
  const aboveR = spot > resistance;
  const belowS = spot < support;
  const nearThreshold = Math.max(100, strikeGap * 2);
  const nearS = distToS < nearThreshold;
  const nearR = distToR < nearThreshold;

  const pct = (value: number) =>
    clamp(((value - support) / bandWidth) * 100, 2, 98);

  const supportPct = pct(support);
  const resistancePct = pct(resistance);
  const spotPct = clamp(((spot - support) / bandWidth) * 100, 2, 98);
  const prevResistancePct =
    typeof previousResistance === "number" ? pct(previousResistance) : null;
  const peWallPct = typeof peWall === "number" ? pct(peWall) : null;
  const ceWallPct = typeof ceWall === "number" ? pct(ceWall) : null;
  const magnetPct = typeof magnet === "number" ? pct(magnet) : null;
  const maxPainPct = typeof maxPain === "number" ? pct(maxPain) : null;
  const overRFillWidthPct = aboveR
    ? clamp(((spot - resistance) / bandWidth) * 100, 2, 10)
    : 0;

  const normalizedMagnetDirection =
    String(magnetPullDirection || "").trim().toLowerCase();
  const normalizedPrevMagnetDirection =
    String(prevMagnetDirection || "").trim().toLowerCase();
  const magnetFlip =
    Boolean(normalizedPrevMagnetDirection) &&
    Boolean(normalizedMagnetDirection) &&
    normalizedPrevMagnetDirection !== normalizedMagnetDirection;

  const magnetArrow =
    typeof magnet !== "number"
      ? ""
      : magnet > spot
        ? "▲"
        : magnet < spot
          ? "▼"
          : "◉";

  const magnetArrowDisplay =
    typeof magnet !== "number"
      ? ""
      : normalizedMagnetDirection === "up"
        ? "â–²"
        : normalizedMagnetDirection === "down"
          ? "â–¼"
          : normalizedMagnetDirection === "at"
            ? "â—‰"
            : magnetArrow;

  const visibleStrikes = (strikes || [])
    .filter(
      (s) =>
        s &&
        Number.isFinite(s.strike) &&
        s.strike >= support &&
        s.strike <= resistance,
    )
    .sort((a, b) => a.strike - b.strike);

  const nearestStrike = visibleStrikes.length
    ? visibleStrikes.reduce((best, current) =>
      Math.abs(current.strike - spot) < Math.abs(best.strike - spot)
        ? current
        : best,
    ).strike
    : null;

  const maxOi = visibleStrikes.reduce(
    (m, s) => Math.max(m, s.oi_ce || 0, s.oi_pe || 0),
    0,
  );
  const barHeight = (value: number) =>
    maxOi > 0 ? Math.max(2, Math.round((Math.max(value, 0) / maxOi) * 16)) : 2;

  const oiRatioMap = useMemo(() => {
    const map: Record<number, {
      ratio: number;
      label: string;
      side: "ce" | "pe" | "neutral";
    }> = {};
    for (const row of visibleStrikes) {
      if (!row || !Number.isFinite(row.strike)) continue;
      const ce = Math.max(0, Number(row.oi_ce) || 0);
      const pe = Math.max(0, Number(row.oi_pe) || 0);
      if (ce <= 0 || pe <= 0) continue;

      const supportSide = row.strike <= spot;
      const ratio = supportSide ? pe / ce : ce / pe;
      const label = supportSide
        ? `ΔPE/ΔCE ${ratio.toFixed(2)}x`
        : `ΔCE/ΔPE ${ratio.toFixed(2)}x`;
      const side = supportSide ? "pe" : "ce";
      map[row.strike] = { ratio, label, side };
    }
    return map;
  }, [chainGreeks, spot]);
  void oiRatioMap;

  const strikeOiDefenseMap = useMemo(() => {
    const map: Record<number, {
      ratio: number;
      label: string;
      side: "ce" | "pe" | "neutral";
    }> = {};
    for (const row of visibleStrikes) {
      if (!row || !Number.isFinite(row.strike)) continue;
      const ce = Math.max(0, Number(row.oi_ce) || 0);
      const pe = Math.max(0, Number(row.oi_pe) || 0);
      if (ce <= 0 || pe <= 0) continue;

      const supportSide = row.strike <= spot;
      const ratio = supportSide ? pe / ce : ce / pe;
      const label = supportSide
        ? `PE/CE ${ratio.toFixed(2)}x`
        : `CE/PE ${ratio.toFixed(2)}x`;
      const side = supportSide ? "pe" : "ce";
      map[row.strike] = { ratio, label, side };
    }
    return map;
  }, [visibleStrikes, spot]);

  const metricToSupportTone =
    nearS || belowS ? "sbb-metric-warn-s" : "sbb-metric-neutral";
  const metricToResistanceTone =
    nearR || aboveR ? "sbb-metric-warn-r" : "sbb-metric-neutral";

  const topLabelStyle = (
    markerPct: number,
    color: string,
  ): Record<string, string | number> => {
    if (markerPct >= 94)
      return { right: "0px", left: "auto", transform: "none", color };
    if (markerPct <= 6) return { left: "0px", transform: "none", color };
    return { left: `${markerPct}%`, color };
  };

  const magnetMaxPainClose =
    magnetPct !== null &&
    maxPainPct !== null &&
    Math.abs(magnetPct - maxPainPct) < 4;

  const belowLabelStyle = (
    markerPct: number,
    color: string,
    stackIndex = 0,
  ): Record<string, string | number> => {
    const baseBottom = -16 - stackIndex * 13;
    if (markerPct >= 94) {
      return {
        right: "0px",
        left: "auto",
        transform: "none",
        color,
        bottom: `${baseBottom}px`,
      };
    }
    if (markerPct <= 6) {
      return {
        left: "0px",
        transform: "none",
        color,
        bottom: `${baseBottom}px`,
      };
    }
    return { left: `${markerPct}%`, color, bottom: `${baseBottom}px` };
  };

  return (
    <div className={`sbb-wrap${embedded ? " sbb-wrap-embedded" : " sbb-panel"}`}>
      {/* ── Stats row: shown only in standalone mode ── */}
      {!embedded && (
        <div className="sbb-stats">
          <div className="sbb-stat sbb-stat-left">
            <span className="sbb-stat-lbl">Support</span>
            <span className="sbb-stat-val sbb-stat-s">S {fmt(support)}</span>
          </div>
          <div className="sbb-stat sbb-stat-center">
            <span className="sbb-stat-lbl">Spot</span>
            <span className="sbb-stat-val sbb-stat-spot">
              {spot.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          </div>
          <div className="sbb-stat sbb-stat-right">
            <span className="sbb-stat-lbl">Resistance</span>
            <span className="sbb-stat-val sbb-stat-r">R {fmt(resistance)}</span>
          </div>
        </div>
      )}

      {/* ── Zone chips: shown only in standalone mode ── */}
      {!embedded && (
        <div className="sbb-zone-row">
          <span className="sbb-zone-chip sbb-zone-chip-support">Defended support</span>
          <span className="sbb-zone-chip sbb-zone-chip-neutral">Active zone</span>
          <span className="sbb-zone-chip sbb-zone-chip-resistance">Resistance watch</span>
        </div>
      )}

      {/* ── Track ── */}
      <div className="band-section">
        <div className="band-outer sbb-track-wrap">
          <div className="band-track sbb-track" />
        {typeof peWall === "number" && peWall >= support ? (
          <div
            className="sbb-fill sbb-fill-support"
            style={{
              left: `${supportPct}%`,
              width: `${Math.max(0, (peWallPct ?? supportPct) - supportPct)}%`,
            }}
          />
        ) : null}
        {typeof ceWall === "number" && ceWall <= resistance ? (
          <div
            className="sbb-fill sbb-fill-resistance"
            style={{
              left: `${ceWallPct ?? resistancePct}%`,
              width: `${Math.max(0, resistancePct - (ceWallPct ?? resistancePct))}%`,
            }}
          />
        ) : null}
        {aboveR ? (
          <div
            className="sbb-overext-right"
            style={{ left: `${resistancePct}%`, width: `${overRFillWidthPct}%` }}
          />
        ) : null}
        <div
          className="sbb-marker"
          style={{ left: `${supportPct}%`, top: "10px", height: "24px", background: "#26a69a" }}
        />
        <div
          className="sbb-marker"
          style={{ left: `${resistancePct}%`, top: "10px", height: "24px", background: "#ef5350" }}
        />
        {prevResistancePct !== null ? (
          <div
            className="sbb-marker"
            style={{ left: `${prevResistancePct}%`, top: "11px", height: "22px", background: "rgba(156,163,175,0.8)" }}
          />
        ) : null}
        {peWallPct !== null ? (
          <div
            className="sbb-marker"
            style={{ left: `${peWallPct}%`, top: "13px", height: "18px", background: "rgba(38,166,154,0.65)" }}
          />
        ) : null}
        {ceWallPct !== null ? (
          <div
            className="sbb-marker"
            style={{ left: `${ceWallPct}%`, top: "13px", height: "18px", background: "rgba(239,83,80,0.65)" }}
          />
        ) : null}
        {magnetPct !== null ? (
          <div
            className="sbb-marker"
            style={{ left: `${magnetPct}%`, top: "8px", height: "28px", background: "#f59e0b" }}
          />
        ) : null}
        {maxPainPct !== null ? (
          <div
            className="sbb-marker"
            style={{ left: `${maxPainPct}%`, top: "12px", height: "20px", borderLeft: "2px dashed #a78bfa" }}
          />
        ) : null}
        <div
          className="sbb-marker"
          style={{ left: `${spotPct}%`, top: "8px", height: "28px", background: "rgba(226,232,240,0.95)" }}
        />
        <div
          className={`sbb-dot ${nearR || aboveR ? "sbb-dot-near-r" : nearS || belowS ? "sbb-dot-near-s" : ""}`}
          style={{ left: `${spotPct}%` }}
        />

        <div className="sbb-lbl-above" style={topLabelStyle(supportPct, "#26a69a")}>
          S {fmt(support)}
        </div>
        <div className="sbb-lbl-above" style={topLabelStyle(resistancePct, "#ef5350")}>
          R {fmt(resistance)}
        </div>
        {prevResistancePct !== null ? (
          <div className="sbb-lbl-above" style={topLabelStyle(prevResistancePct, "#9ca3af")}>
            Prev R {fmt(previousResistance)}
          </div>
        ) : null}
        {magnetPct !== null ? (
          <div
            className="sbb-lbl-below"
            style={belowLabelStyle(
              magnetPct,
              "#f59e0b",
              magnetMaxPainClose && maxPainPct !== null && magnetPct >= maxPainPct ? 1 : 0,
            )}
          >
            magnet
          </div>
        ) : null}
        {maxPainPct !== null ? (
          <div
            className="sbb-lbl-below"
            style={belowLabelStyle(
              maxPainPct,
              "#a78bfa",
              magnetMaxPainClose && magnetPct !== null && maxPainPct > magnetPct ? 1 : 0,
            )}
          >
            max pain
          </div>
        ) : null}
        </div>
      </div>

      {/* ── Metrics strip ── */}
      <div className="sbb-metrics-strip">
        <div className="sbb-metric-item sbb-metric-magnet">
          <span className="sbb-metric-lbl">
            Magnet
            {magnetFlip ? (
              <span
                className="sbb-magnet-flip"
                title={`Magnet flipped from ${normalizedPrevMagnetDirection} to ${normalizedMagnetDirection}`}
              >
                â†• flip
              </span>
            ) : null}
          </span>
          <span className="sbb-metric-val sbb-stat-magnet">
            {typeof magnet === "number" ? `${fmt(magnet)} ${magnetArrowDisplay}` : "-"}
          </span>
          {magnetCharacter ? (
            <span className="sbb-metric-sub">
              {String(magnetCharacter).replace(/[_-]+/g, " ")}
            </span>
          ) : null}
        </div>
        <div className="sbb-metric-item sbb-metric-maxpain">
          <span className="sbb-metric-lbl">Max pain</span>
          <span className="sbb-metric-val sbb-stat-maxpain">
            {typeof maxPain === "number" ? fmt(maxPain) : "-"}
          </span>
        </div>
        <div className="sbb-metric-item">
          <span className="sbb-metric-lbl">Band</span>
          <span className="sbb-metric-val">{fmt(bandWidth)} pts</span>
        </div>
        <div className={`sbb-metric-item sbb-metric-support ${metricToSupportTone}`}>
          <span className="sbb-metric-lbl">To support</span>
          <span className="sbb-metric-val">
            {belowS ? `-${fmt(Math.abs(distToS))} pts` : `${fmt(distToS)} pts`}
          </span>
        </div>
        <div className={`sbb-metric-item sbb-metric-resistance ${metricToResistanceTone}`}>
          <span className="sbb-metric-lbl">To resist</span>
          <span className="sbb-metric-val">
            {aboveR ? `+${fmt(Math.abs(distToR))} pts` : `${fmt(distToR)} pts`}
          </span>
        </div>
      </div>

      {/* ── Strike OI mini-bars ── */}
      {visibleStrikes.length > 0 ? (
        <div className="sbb-strikes">
          {visibleStrikes.map((s) => {
            const d = strikeOiDefenseMap[s.strike];
            return (
              <div key={s.strike} className="sbb-strike-cell">
                <span className={`sbb-strike-num ${nearestStrike === s.strike ? "sbb-strike-num-active" : ""}`}>
                  {fmt(s.strike)}
                </span>
                <div className="sbb-minibars">
                  <div className="sbb-bar-pe" style={{ height: `${barHeight(s.oi_pe || 0)}px` }} />
                  <div className="sbb-bar-ce" style={{ height: `${barHeight(s.oi_ce || 0)}px` }} />
                </div>
                {d ? (
                  <div className={`sb-strike-delta sb-strike-delta-${d.side}`}>
                    <span className="sb-strike-delta-dot" />
                    <span className="sb-strike-delta-label">{d.label}</span>
                  </div>
                ) : null}
                {s.tag === "pe_wall" ? <span className="sbb-tag sbb-tag-pe">PE wall</span> : null}
                {s.tag === "ce_wall" ? <span className="sbb-tag sbb-tag-ce">CE wall</span> : null}
                {s.tag === "magnet" ? <span className="sbb-tag sbb-tag-magnet">magnet</span> : null}
                {s.tag === "maxpain" ? <span className="sbb-tag sbb-tag-maxpain">max pain</span> : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* ── Legend ── */}
      <div className="sbb-legend">
        <span className="sbb-leg-item">
          <span className="sbb-leg-line" style={{ background: "#26a69a" }} />
          PE wall / S
        </span>
        <span className="sbb-leg-item">
          <span className="sbb-leg-line" style={{ background: "#ef5350" }} />
          CE wall / R
        </span>
        <span className="sbb-leg-item">
          <span className="sbb-leg-line" style={{ background: "#f59e0b" }} />
          Magnet
        </span>
        <span className="sbb-leg-item">
          <span className="sbb-leg-dash" />
          Max pain
        </span>
        <span className="sbb-leg-item">
          <span className="sbb-leg-line" style={{ background: "#94a3b8" }} />
          Prev R
        </span>
        <span className="sbb-leg-item">
          <span className="sbb-leg-dot" style={{ background: "rgba(226,232,240,0.95)" }} />
          Spot
        </span>
      </div>
    </div>
  );
}
