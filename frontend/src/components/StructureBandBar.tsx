import { useMemo } from "react";

type StrikePoint = {
  strike: number;
  oi_ce: number;
  oi_pe: number;
  tag?: "pe_wall" | "ce_wall" | "magnet" | "maxpain" | null;
};

type LadderPressure =
  | "strong_support"
  | "support"
  | "balanced"
  | "resistance"
  | "strong_resistance";

type NextMoveBias = "UP" | "DOWN" | "PINNED" | "NO_EDGE";

type StrikePressure = {
  pePct: number;
  cePct: number;
  peCe: number;
  cePe: number;
  state: LadderPressure;
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
  embedded?: boolean;
  trapProbability?: number | null;
  materialBreachConfirmed?: boolean;
  absorptionStrength?: number | null;
  absorptionSignal?: string | null;
};

const fmt = (value?: number | null) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-IN", { maximumFractionDigits: 0 })
    : "-";

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

function resolveLadderPressure(ceOi: number, peOi: number): LadderPressure {
  const ce = Math.max(0, Number(ceOi) || 0);
  const pe = Math.max(0, Number(peOi) || 0);
  const total = ce + pe;
  if (total <= 0) return "balanced";
  const pePct = pe / total;
  const cePct = ce / total;
  if (pePct >= 0.65) return "strong_support";
  if (pePct >= 0.55) return "support";
  if (cePct >= 0.65) return "strong_resistance";
  if (cePct >= 0.55) return "resistance";
  return "balanced";
}

function computeStrikePressure(ceOi: number, peOi: number): StrikePressure {
  const ce = Math.max(0, Number(ceOi) || 0);
  const pe = Math.max(0, Number(peOi) || 0);
  const total = ce + pe;
  const pePct = total > 0 ? pe / total : 0.5;
  const cePct = total > 0 ? ce / total : 0.5;
  return {
    pePct,
    cePct,
    peCe: pe / Math.max(ce, 1),
    cePe: ce / Math.max(pe, 1),
    state: resolveLadderPressure(ce, pe),
  };
}

function hasSupport(state: LadderPressure) {
  return state === "support" || state === "strong_support";
}

function hasResistance(state: LadderPressure) {
  return state === "resistance" || state === "strong_resistance";
}

function isStrong(state: LadderPressure) {
  return state === "strong_support" || state === "strong_resistance";
}

function resolveNextMoveBias(
  below: StrikePressure | null,
  center: StrikePressure | null,
  above: StrikePressure | null,
): { bias: NextMoveBias; confidence: number; reason: string } {
  if (!below || !center || !above) {
    return {
      bias: "NO_EDGE",
      confidence: 40,
      reason: "Nearby PE/CE and CE/PE pressure does not show a clean next move.",
    };
  }

  const centerSupport = hasSupport(center.state);
  const centerResistance = hasResistance(center.state);
  const centerBalanced = center.state === "balanced";
  const belowSupport = hasSupport(below.state);
  const belowResistance = hasResistance(below.state);
  const aboveSupport = hasSupport(above.state);
  const aboveResistance = hasResistance(above.state);
  const aboveStrongResistance = above.state === "strong_resistance";

  let base = 50;
  let reason = "Nearby PE/CE and CE/PE pressure does not show a clean next move.";

  // 1) PINNED
  if (
    belowSupport &&
    aboveResistance &&
    (centerBalanced || center.state === "support" || center.state === "resistance")
  ) {
    base = 55;
    if (isStrong(below.state)) base += 8;
    if (isStrong(above.state)) base += 8;
    reason = "Spot is trapped between nearby support and resistance pressure.";
    return { bias: "PINNED", confidence: clamp(Math.round(base), 0, 100), reason };
  }

  // 2) UP
  if (centerSupport && belowSupport && !aboveStrongResistance) {
    base = 55;
    if (isStrong(center.state)) base += 15;
    else base += 8;
    if (isStrong(below.state)) base += 15;
    else base += 8;
    if (aboveResistance) base -= 10;
    reason = "Put-side support is defending near spot and overhead call pressure is not dominant.";
    return { bias: "UP", confidence: clamp(Math.round(base), 0, 100), reason };
  }
  if ((above.state === "balanced" || aboveSupport) && center.pePct >= 0.55 && below.pePct >= 0.55) {
    base = 58;
    if (center.pePct >= 0.65) base += 10;
    if (below.pePct >= 0.65) base += 10;
    reason = "Put-side pressure dominates around spot with limited overhead resistance.";
    return { bias: "UP", confidence: clamp(Math.round(base), 0, 100), reason };
  }

  // 3) DOWN
  if (centerResistance) {
    base = 56;
    if (isStrong(center.state)) base += 15;
    else base += 8;
    if (belowSupport) base -= 10;
    reason = "Call-side pressure is active at the spot strike.";
    return { bias: "DOWN", confidence: clamp(Math.round(base), 0, 100), reason };
  }
  if ((below.state === "balanced" || belowResistance) && (centerBalanced || centerResistance)) {
    base = 57;
    if (isStrong(below.state)) base += 15;
    else if (belowResistance) base += 8;
    if (aboveSupport) base -= 10;
    reason = "Support below spot is weak, allowing downside drift.";
    return { bias: "DOWN", confidence: clamp(Math.round(base), 0, 100), reason };
  }
  if (aboveStrongResistance && center.state !== "strong_support") {
    base = 60;
    if (centerSupport) base -= 10;
    reason = "Strong call-side pressure overhead may reject spot lower.";
    return { bias: "DOWN", confidence: clamp(Math.round(base), 0, 100), reason };
  }

  // 4) NO_EDGE
  return {
    bias: "NO_EDGE",
    confidence: 40,
    reason,
  };
}

const resolveMagnetSub = (
  magnet: number | null | undefined,
  spot: number,
  strikeGap: number,
  magnetCharacter: string | null | undefined,
): string | null => {
  if (typeof magnet !== "number" || !Number.isFinite(magnet)) return null;
  const delta = Math.round(magnet - spot);
  if (delta === 0) return "at spot";
  const arrow = delta < 0 ? "down" : "up";
  const pts = Math.abs(delta);
  const where = delta < 0 ? "below" : "above";
  const gapMultiple = strikeGap > 0 ? pts / strikeGap : 0;
  const characterText = magnetCharacter
    ? ` · ${String(magnetCharacter).replace(/[_-]+/g, " ").toLowerCase()}`
    : "";
  if (gapMultiple < 0.75) return `${arrow} ${pts} pts ${where}${characterText}`;
  return `${arrow} ${pts} pts ${where}${characterText}`;
};

const resolveMaxPainSub = (
  maxPain: number | null | undefined,
  magnet: number | null | undefined,
  spot: number,
): string | null => {
  if (typeof maxPain !== "number" || !Number.isFinite(maxPain)) return null;
  if (typeof magnet === "number" && Math.round(magnet) === Math.round(maxPain))
    return "= magnet";
  const delta = Math.round(maxPain - spot);
  if (delta === 0) return "at spot";
  const arrow = delta < 0 ? "down" : "up";
  return `${arrow} ${Math.abs(delta)} pts`;
};

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
  trapProbability = null,
  materialBreachConfirmed = false,
  absorptionStrength = null,
  absorptionSignal = null,
}: StructureBandBarProps) {
  void chainGreeks;

  const bandWidth = resistance - support;
  if (!Number.isFinite(bandWidth) || bandWidth <= 0) return null;

  const distToS = Math.round(spot - support);
  const distToR = Math.round(resistance - spot);
  const aboveR = spot > resistance;
  const belowS = spot < support;
  const nearThreshold = Math.max(100, strikeGap * 2);
  const nearS = distToS < nearThreshold;
  const nearR = distToR < nearThreshold;
  const spotInsideRange = !aboveR && !belowS;

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

  const rubberBandActive = aboveR || belowS;
  const brokenLevel = aboveR ? resistance : belowS ? support : null;
  const tensionPx =
    rubberBandActive && brokenLevel !== null ? Math.abs(spot - brokenLevel) : 0;
  const tensionScale = Math.max(50, strikeGap * 2);
  const tension = clamp(tensionPx / tensionScale, 0, 1);

  const rubberSnapAnchorPct = rubberBandActive
    ? aboveR
      ? 72
      : 28
    : null;

  const rubberSpotPct = rubberBandActive
    ? aboveR
      ? 72 + tension * 26
      : 28 - tension * 26
    : spotPct;

  const rejectionRisk =
    rubberBandActive &&
    tension >= 0.65 &&
    (typeof trapProbability === "number" && trapProbability >= 55);

  const absorptionScore =
    typeof absorptionStrength === "number" && Number.isFinite(absorptionStrength)
      ? clamp(Math.round(absorptionStrength), 0, 100)
      : 0;
  const absorptionBand =
    absorptionScore >= 76
      ? "extreme"
      : absorptionScore >= 51
        ? "strong"
        : absorptionScore >= 26
          ? "moderate"
          : "weak";
  const absorptionLabel =
    absorptionBand === "extreme"
      ? "Extreme"
      : absorptionBand === "strong"
        ? "Strong"
        : absorptionBand === "moderate"
          ? "Mild"
          : "Weak";
  const absorptionSignalLabel = String(absorptionSignal || "")
    .trim()
    .replace(/[_-]+/g, " ")
    .toLowerCase();
  const showAbsorptionPill = absorptionScore > 25;

  const haloOpacity = rubberBandActive ? 0.4 + tension * 0.5 : 0.25;
  const markerWidthPx = rubberBandActive ? 1 + Math.round(tension * 2) : 1;

  const normalizedMagnetDirection =
    String(magnetPullDirection || "").trim().toLowerCase();
  const normalizedPrevMagnetDirection =
    String(prevMagnetDirection || "").trim().toLowerCase();
  const magnetFlip =
    Boolean(normalizedPrevMagnetDirection) &&
    Boolean(normalizedMagnetDirection) &&
    normalizedPrevMagnetDirection !== normalizedMagnetDirection;

  const allSortedStrikes = (strikes || [])
    .filter((s) => s && Number.isFinite(s.strike))
    .sort((a, b) => a.strike - b.strike);

  const nearestStrike = allSortedStrikes.length
    ? allSortedStrikes.reduce((best, current) =>
      Math.abs(current.strike - spot) < Math.abs(best.strike - spot)
        ? current
        : best,
    ).strike
    : null;
  const displaySpotStrike =
    Number.isFinite(spot) && strikeGap > 0
      ? Math.round(spot / strikeGap) * strikeGap
      : nearestStrike;
  const spotStrikeForLadder =
    typeof displaySpotStrike === "number" && Number.isFinite(displaySpotStrike)
      ? displaySpotStrike
      : (typeof nearestStrike === "number" ? nearestStrike : null);

  const ladderStrikes = useMemo(() => {
    if (spotStrikeForLadder == null || !Number.isFinite(strikeGap) || strikeGap <= 0) return [];

    const byStrike = new Map<number, StrikePoint>();
    for (const s of allSortedStrikes) {
      byStrike.set(s.strike, s);
    }

    const rangeStart = Math.floor(Math.min(support, resistance) / strikeGap) * strikeGap;
    const rangeEnd = Math.ceil(Math.max(support, resistance) / strikeGap) * strikeGap;
    const required = new Set<number>();
    for (let k = rangeStart; k <= rangeEnd; k += strikeGap) required.add(k);
    // Always include spot strike and one strike on each side.
    required.add(spotStrikeForLadder);
    required.add(spotStrikeForLadder - strikeGap);
    required.add(spotStrikeForLadder + strikeGap);

    const resolveTag = (strike: number): StrikePoint["tag"] => {
      if (typeof peWall === "number" && strike === peWall) return "pe_wall";
      if (typeof ceWall === "number" && strike === ceWall) return "ce_wall";
      if (typeof magnet === "number" && strike === Math.round(magnet / strikeGap) * strikeGap) return "magnet";
      if (typeof maxPain === "number" && strike === Math.round(maxPain / strikeGap) * strikeGap) return "maxpain";
      return null;
    };

    const built: StrikePoint[] = [...required]
      .sort((a, b) => a - b)
      .map((strike) => {
        const row = byStrike.get(strike);
        return {
          strike,
          oi_ce: row?.oi_ce ?? 0,
          oi_pe: row?.oi_pe ?? 0,
          tag: row?.tag ?? resolveTag(strike),
        };
      });
    return built;
  }, [allSortedStrikes, support, resistance, spotStrikeForLadder, strikeGap, peWall, ceWall, magnet, maxPain]);

  const maxOi = ladderStrikes.reduce(
    (m, s) => Math.max(m, s.oi_ce || 0, s.oi_pe || 0),
    0,
  );
  const barHeight = (value: number) =>
    maxOi > 0 ? Math.max(2, Math.round((Math.max(value, 0) / maxOi) * 16)) : 2;

  const strikeOiDefenseMap = useMemo(() => {
    const map: Record<number, {
      ratio: number;
      label: string;
      side: "ce" | "pe" | "neutral";
    }> = {};
    for (const row of allSortedStrikes) {
      if (!row || !Number.isFinite(row.strike)) continue;
      const ce = Math.max(0, Number(row.oi_ce) || 0);
      const pe = Math.max(0, Number(row.oi_pe) || 0);
      if (ce <= 0 || pe <= 0) continue;

      const supportSide = row.strike <= spot;
      const ratio = supportSide ? pe / ce : ce / pe;
      const label = supportSide
        ? `PE/CE ${ratio.toFixed(2)}x`
        : `CE/PE ${ratio.toFixed(2)}x`;
      const side =
        ratio >= 1.1 ? (supportSide ? "pe" : "ce") : ratio <= 0.9 ? (supportSide ? "ce" : "pe") : "neutral";
      map[row.strike] = { ratio, label, side };
    }
    return map;
  }, [allSortedStrikes, spot]);

  const metricToSupportTone =
    nearS || belowS ? "sbb-metric-warn-s" : "sbb-metric-neutral";
  const metricToResistanceTone =
    nearR || aboveR ? "sbb-metric-warn-r" : "sbb-metric-neutral";

  const nextMove = useMemo(() => {
    if (spotStrikeForLadder == null || ladderStrikes.length === 0) {
      return {
        bias: "NO_EDGE" as NextMoveBias,
        confidence: 40,
        reason: "Nearby PE/CE and CE/PE pressure does not show a clean next move.",
      };
    }
    const centerIdx = ladderStrikes.findIndex((s) => s.strike === spotStrikeForLadder);
    if (centerIdx < 0) {
      return {
        bias: "NO_EDGE" as NextMoveBias,
        confidence: 40,
        reason: "Nearby PE/CE and CE/PE pressure does not show a clean next move.",
      };
    }
    const below = centerIdx > 0 ? ladderStrikes[centerIdx - 1] : null;
    const center = ladderStrikes[centerIdx];
    const above = centerIdx < ladderStrikes.length - 1 ? ladderStrikes[centerIdx + 1] : null;
    return resolveNextMoveBias(
      below ? computeStrikePressure(below.oi_ce || 0, below.oi_pe || 0) : null,
      center ? computeStrikePressure(center.oi_ce || 0, center.oi_pe || 0) : null,
      above ? computeStrikePressure(above.oi_ce || 0, above.oi_pe || 0) : null,
    );
  }, [ladderStrikes, spotStrikeForLadder]);

  const nextMoveToneClass =
    nextMove.bias === "UP"
      ? "sbb-next-bias--up"
      : nextMove.bias === "DOWN"
        ? "sbb-next-bias--down"
        : nextMove.bias === "PINNED"
          ? "sbb-next-bias--pinned"
          : "sbb-next-bias--noedge";
  const nextMoveSymbol =
    nextMove.bias === "UP" ? "↑" : nextMove.bias === "DOWN" ? "↓" : nextMove.bias === "PINNED" ? "↔" : "·";
  const spotArrow = useMemo(() => {
    if (nextMove.bias === "UP") {
      return {
        symbol: "▲",
        cls: "ladder-pressure-arrow--strong-support",
        title: `Next move bias UP (${nextMove.confidence}%)`,
      };
    }
    if (nextMove.bias === "DOWN") {
      return {
        symbol: "▼",
        cls: "ladder-pressure-arrow--strong-resistance",
        title: `Next move bias DOWN (${nextMove.confidence}%)`,
      };
    }
    if (nextMove.bias === "PINNED") {
      return {
        symbol: "↔",
        cls: "ladder-pressure-arrow--balanced",
        title: `Next move bias PINNED (${nextMove.confidence}%)`,
      };
    }
    return {
      symbol: "·",
      cls: "ladder-pressure-arrow--balanced",
      title: "Next move bias NO_EDGE",
    };
  }, [nextMove.bias, nextMove.confidence]);

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

      {!embedded && (
        <div className="sbb-zone-row">
          <span className="sbb-zone-chip sbb-zone-chip-support">Defended support</span>
          <span className="sbb-zone-chip sbb-zone-chip-neutral">Active zone</span>
          <span className="sbb-zone-chip sbb-zone-chip-resistance">Resistance watch</span>
        </div>
      )}

      <div className={`band-section${rubberBandActive ? " band-section-rubber" : ""}${rejectionRisk ? " band-section-rejection" : ""}${showAbsorptionPill ? ` sbb-absorption-${absorptionBand}` : ""}`}>
        {showAbsorptionPill ? (
          <div className={`sbb-absorption-pill sbb-absorption-pill-${absorptionBand}`}>
            {`Absorption ${absorptionLabel} (${absorptionScore})`}
            {absorptionSignalLabel ? ` · ${absorptionSignalLabel}` : ""}
          </div>
        ) : null}
        {spotInsideRange ? (
          <div className="sbb-sr-inside-note">SPOT INSIDE S/R BAND</div>
        ) : null}
        {rubberBandActive ? (
          <div className={`sbb-rubber-status${rejectionRisk ? " sbb-rubber-status-risk" : ""}`}>
            <span className="sbb-rubber-state">
              {aboveR ? "Above R" : "Below S"}
            </span>
            <span className="sbb-rubber-tension">
              tension {tension.toFixed(2)}
            </span>
            {materialBreachConfirmed ? (
              <span className="sbb-rubber-badge sbb-rubber-badge-accept">Acceptance</span>
            ) : rejectionRisk ? (
              <span className="sbb-rubber-badge sbb-rubber-badge-reject">Rejection risk</span>
            ) : null}
          </div>
        ) : null}
        <div className="band-outer sbb-track-wrap">
          <div className="band-track sbb-track" />
          {rubberBandActive && brokenLevel !== null && rubberSnapAnchorPct !== null ? (
            <>
              <div
                className={`sbb-tether sbb-tether-${aboveR ? "right" : "left"}`}
                style={{
                  left: aboveR ? `${rubberSnapAnchorPct}%` : `${rubberSpotPct}%`,
                  right: aboveR ? `${100 - rubberSpotPct}%` : undefined,
                  width: aboveR ? undefined : `${rubberSnapAnchorPct - rubberSpotPct}%`,
                  opacity: 0.3 + tension * 0.55,
                }}
                aria-hidden="true"
              />
              <div
                className={`sbb-snap-marker sbb-snap-marker-${aboveR ? "right" : "left"}`}
                style={{
                  left: `${rubberSnapAnchorPct}%`,
                  width: `${markerWidthPx}px`,
                  boxShadow: tension >= 0.6 ? "0 0 8px rgba(239,83,80,0.6)" : undefined,
                }}
                aria-hidden="true"
              />
              <div
                className={`sbb-snap-label sbb-snap-label-${aboveR ? "right" : "left"}`}
                style={{ left: `${rubberSnapAnchorPct}%` }}
              >
                SNAP
              </div>
            </>
          ) : null}
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
            style={{
              left: `${rubberBandActive ? rubberSpotPct : spotPct}%`,
              boxShadow: rubberBandActive
                ? `0 0 ${10 + tension * 14}px rgba(${aboveR ? "239,83,80" : "38,166,154"},${haloOpacity})${rejectionRisk ? ", 0 0 0 4px rgba(239,83,80,0.25), 0 0 0 8px rgba(239,83,80,0.12)" : ""}`
                : undefined,
            }}
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

      <div className="sbb-metrics-strip">
        <div
          className={`sbb-next-bias ${nextMoveToneClass}`}
          title={nextMove.reason}
          aria-label={nextMove.reason}
        >
          <span className="sbb-next-bias-label">Next bias</span>
          <span className="sbb-next-bias-value">
            {nextMoveSymbol} {nextMove.bias}
            {nextMove.bias !== "NO_EDGE" ? ` ${nextMove.confidence}%` : ""}
          </span>
        </div>
        <div className="sbb-metric-item sbb-metric-magnet">
          <span className="sbb-metric-lbl">
            Magnet
            {magnetFlip ? (
              <span
                className="sbb-magnet-flip"
                title={`Magnet flipped from ${normalizedPrevMagnetDirection} to ${normalizedMagnetDirection}`}
              >
                ↕ flip
              </span>
            ) : null}
          </span>
          <span className="sbb-metric-val sbb-stat-magnet">
            {typeof magnet === "number" ? fmt(magnet) : "-"}
          </span>
          {(() => {
            const sub = resolveMagnetSub(magnet, spot, strikeGap, magnetCharacter);
            return sub ? <span className="sbb-metric-sub">{sub}</span> : null;
          })()}
        </div>
        <div className="sbb-metric-item sbb-metric-maxpain">
          <span className="sbb-metric-lbl">Max pain</span>
          <span className="sbb-metric-val sbb-stat-maxpain">
            {typeof maxPain === "number" ? fmt(maxPain) : "-"}
          </span>
          {(() => {
            const sub = resolveMaxPainSub(maxPain, magnet, spot);
            return sub ? <span className="sbb-metric-sub">{sub}</span> : null;
          })()}
        </div>
        <div className="sbb-metric-item">
          <span className="sbb-metric-lbl">Band</span>
          <span className="sbb-metric-val">{fmt(bandWidth)} pts</span>
          <span className="sbb-metric-sub">S to R width</span>
        </div>
        <div className={`sbb-metric-item sbb-metric-support ${metricToSupportTone}`}>
          <span className="sbb-metric-lbl">To support</span>
          <span className="sbb-metric-val">
            {belowS ? `-${fmt(Math.abs(distToS))} pts` : `${fmt(distToS)} pts`}
          </span>
          {bandWidth > 0 && !belowS ? (
            <span className="sbb-metric-sub">
              {Math.round((distToS / bandWidth) * 100)}% of band
            </span>
          ) : null}
        </div>
        <div
          className={`sbb-metric-item sbb-metric-resistance ${metricToResistanceTone}${
            !aboveR && !belowS && bandWidth > 0 && distToR / bandWidth < 0.2
              ? " sbb-metric-edge"
              : ""
          }`}
        >
          <span className="sbb-metric-lbl">To resist</span>
          <span className="sbb-metric-val">
            {aboveR ? `+${fmt(Math.abs(distToR))} pts` : `${fmt(distToR)} pts`}
          </span>
          {bandWidth > 0 && !aboveR ? (
            <span className="sbb-metric-sub">
              {distToR / bandWidth < 0.2
                ? `${Math.round((distToR / bandWidth) * 100)}% - edge zone`
                : `${Math.round((distToR / bandWidth) * 100)}% of band`}
            </span>
          ) : null}
        </div>
      </div>

      {ladderStrikes.length > 0 ? (
        <div className="sbb-strikes sbb-strikes-v2">
          {ladderStrikes.map((s) => {
            const d = strikeOiDefenseMap[s.strike];
            const isSpot = spotStrikeForLadder === s.strike;
            const hasWallTag =
              s.tag === "pe_wall" || s.tag === "ce_wall" || s.tag === "magnet" || s.tag === "maxpain";
            return (
              <div
                key={s.strike}
                className={`sbb-strike-cell${isSpot ? " sbb-strike-cell-spot" : ""}${hasWallTag ? ` sbb-strike-cell-${s.tag}` : ""}`}
              >
                {isSpot ? (
                  <span
                    className={`ladder-pressure-arrow ${spotArrow.cls}`}
                    title={spotArrow.title}
                    aria-label={spotArrow.title}
                  >
                    {spotArrow.symbol}
                  </span>
                ) : null}
                <span className={`sbb-strike-num ${isSpot ? "sbb-strike-num-active" : ""}`}>
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
                {isSpot && !hasWallTag ? <span className="sbb-tag sbb-tag-spot">SPOT</span> : null}
                {s.tag === "pe_wall" ? <span className="sbb-tag sbb-tag-pe sbb-tag-v2">PE WALL</span> : null}
                {s.tag === "ce_wall" ? <span className="sbb-tag sbb-tag-ce sbb-tag-v2">CE WALL</span> : null}
                {s.tag === "magnet" ? <span className="sbb-tag sbb-tag-magnet sbb-tag-v2">MAGNET</span> : null}
                {s.tag === "maxpain" ? <span className="sbb-tag sbb-tag-maxpain sbb-tag-v2">MAX PAIN</span> : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* legend removed in v2 - wall tags self-document */}
    </div>
  );
}
