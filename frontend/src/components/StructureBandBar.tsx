import { useMemo } from "react";

type StrikePoint = {
  strike: number;
  oi_ce: number;
  oi_pe: number;
  oi_ce_change?: number | null;
  oi_pe_change?: number | null;
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
  magnetInterpretation?: string | null;
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

type TriggerHint = {
  direction: "UP" | "DOWN" | "FLAT" | "CONFLICT";
  confidence: "strong" | "moderate" | "weak";
  ratioLabel: string;
  biasLine: string;
  triggerLine: string;
  deltaLine: string | null;
};

function resolveRatioLabel(
  oi_ce: number,
  oi_pe: number,
): { label: string; ratio: number; dominant: "ce" | "pe" | "balanced" } {
  const ce = Math.max(oi_ce, 1);
  const pe = Math.max(oi_pe, 1);
  const ratio = ce / pe;
  const dominant =
    ratio > 1.05 ? "ce"
    : ratio < 0.95 ? "pe"
    : "balanced";
  return {
    label: `CE/PE ${ratio.toFixed(2)}x`,
    ratio,
    dominant,
  };
}

function resolveDeltaLine(
  oi_ce_change: number | null | undefined,
  oi_pe_change: number | null | undefined,
): string | null {
  const DELTA_THRESHOLD = 0.02;
  const ce = typeof oi_ce_change === "number" ? oi_ce_change : null;
  const pe = typeof oi_pe_change === "number" ? oi_pe_change : null;
  if (ce === null && pe === null) return null;
  if (Math.abs(pe ?? 0) < DELTA_THRESHOLD && Math.abs(ce ?? 0) < DELTA_THRESHOLD) return null;
  const sign = (v: number) => (v > 0 ? "+" : "");
  const parts: string[] = [];
  if (pe !== null) parts.push(`PE Δ${sign(pe)}${(pe * 100).toFixed(1)}%`);
  if (ce !== null) parts.push(`CE Δ${sign(ce)}${(ce * 100).toFixed(1)}%`);
  return parts.join(" / ");
}

function resolveSpotTrigger(
  strike: number,
  spot: number,
  spotStrike: number,
  oi_ce: number,
  oi_pe: number,
  oi_ce_change: number | null | undefined,
  oi_pe_change: number | null | undefined,
  strikeGap: number,
): TriggerHint {
  void strikeGap;
  void spot;
  const { label, ratio, dominant } = resolveRatioLabel(oi_ce, oi_pe);
  const deltaLine = resolveDeltaLine(oi_ce_change, oi_pe_change);

  const ceDelta = typeof oi_ce_change === "number" ? oi_ce_change : 0;
  const peDelta = typeof oi_pe_change === "number" ? oi_pe_change : 0;

  const ceBuilding = ceDelta > 0.02;
  const peBuilding = peDelta > 0.02;
  const ceUnwinding = ceDelta < -0.02;
  const peUnwinding = peDelta < -0.02;

  // Use strike-aligned spot reference — not raw price — to avoid
  // boundary errors (e.g. strike 23,900 > raw spot 23,898.xx)
  const isAboveSpot = strike > spotStrike;
  const isBelowSpot = strike < spotStrike;

  if (isBelowSpot) {
    if (dominant === "pe") {
      const floorStrength = ratio < 0.5 ? "strong" : ratio < 0.8 ? "moderate" : "weak";
      const flipRatio = ratio < 0.5 ? "0.75" : "1.0";
      if (peUnwinding) {
        return {
          direction: "DOWN",
          confidence: "moderate",
          ratioLabel: label,
          biasLine: "PE exiting below spot · floor weakening",
          triggerLine: "Breakdown risk if CE/PE rises above 1.0x",
          deltaLine,
        };
      }
      return {
        direction: "UP",
        confidence: floorStrength,
        ratioLabel: label,
        biasLine: "PE defending below spot · floor holding",
        triggerLine: `Floor breaks if CE/PE rises above ${flipRatio}x`,
        deltaLine,
      };
    }
    if (dominant === "ce") {
      const flipRatio = ratio > 2.0 ? (ratio * 0.6).toFixed(1) : "1.0";
      if (ceUnwinding) {
        return {
          direction: "UP",
          confidence: "moderate",
          ratioLabel: label,
          biasLine: "CE exiting below spot · bearish pressure easing",
          triggerLine: "Recovery if CE/PE drops below 1.0x",
          deltaLine,
        };
      }
      return {
        direction: "DOWN",
        confidence: ratio > 1.5 ? "strong" : "moderate",
        ratioLabel: label,
        biasLine: "CE dominant below spot · no floor defense",
        triggerLine: `Recovery only if CE/PE drops below ${flipRatio}x`,
        deltaLine,
      };
    }
    const signal = peBuilding
      ? "PE building · floor may strengthen"
      : ceBuilding
        ? "CE building below · watch for floor failure"
        : "Balanced below spot · no clear pressure";
    return {
      direction: peBuilding ? "UP" : ceBuilding ? "DOWN" : "FLAT",
      confidence: "weak",
      ratioLabel: label,
      biasLine: signal,
      triggerLine: "Watch for CE/PE to diverge from 1.0x",
      deltaLine,
    };
  }

  if (isAboveSpot) {
    if (dominant === "ce") {
      const ceilStrength = ratio > 3.0 ? "strong" : ratio > 1.5 ? "moderate" : "weak";
      const flipRatio = ratio > 3.0 ? (ratio * 0.5).toFixed(1) : "1.0";
      if (ceUnwinding) {
        return {
          direction: "UP",
          confidence: "moderate",
          ratioLabel: label,
          biasLine: "CE exiting above spot · ceiling cracking",
          triggerLine: `Breakout if CE/PE drops below ${flipRatio}x`,
          deltaLine,
        };
      }
      return {
        direction: "DOWN",
        confidence: ceilStrength,
        ratioLabel: label,
        biasLine: "CE defending above spot · ceiling holds",
        triggerLine: `Breakout only if CE/PE drops below ${flipRatio}x`,
        deltaLine,
      };
    }
    if (dominant === "pe") {
      const flipRatio = "1.0";
      if (peUnwinding) {
        return {
          direction: "DOWN",
          confidence: "weak",
          ratioLabel: label,
          biasLine: "PE exiting above spot · bullish case weakening",
          triggerLine: "Watch: if CE/PE rises above 1.0x, ceiling reasserts",
          deltaLine,
        };
      }
      return {
        direction: "UP",
        confidence: ratio < 0.6 ? "moderate" : "weak",
        ratioLabel: label,
        biasLine: "PE dominant above spot · ceiling thin",
        triggerLine: `Bullish case fails if CE/PE rises above ${flipRatio}x`,
        deltaLine,
      };
    }
    const signal = ceBuilding
      ? "CE building above · ceiling may strengthen"
      : peBuilding
        ? "PE building above · ceiling thinning"
        : "Balanced above spot · ceiling not clearly defined";
    return {
      direction: ceBuilding ? "DOWN" : peBuilding ? "UP" : "FLAT",
      confidence: "weak",
      ratioLabel: label,
      biasLine: signal,
      triggerLine: "Watch for CE/PE to diverge from 1.0x",
      deltaLine,
    };
  }

  // At spot strike
  if (dominant === "pe") {
    const strength = ratio < 0.5 ? "strong" : ratio < 0.8 ? "moderate" : "weak";
    if (peUnwinding) {
      return {
        direction: "DOWN",
        confidence: "moderate",
        ratioLabel: label,
        biasLine: "PE unwinding at spot · buyers exiting",
        triggerLine: "Watch: CE/PE rising toward 1.0x signals reversal",
        deltaLine,
      };
    }
    if (ceBuilding) {
      return {
        direction: "CONFLICT",
        confidence: "weak",
        ratioLabel: label,
        biasLine: "PE dominant but CE building · tug of war at spot",
        triggerLine: "CE/PE must stay below 0.9x to keep bullish bias",
        deltaLine,
      };
    }
    return {
      direction: "UP",
      confidence: strength,
      ratioLabel: label,
      biasLine: "PE dominant at spot · buyers in control",
      triggerLine: "Bias flips bearish if CE/PE rises above 1.0x",
      deltaLine,
    };
  }

  if (dominant === "ce") {
    const strength = ratio > 2.5 ? "strong" : ratio > 1.5 ? "moderate" : "weak";
    if (ceUnwinding) {
      return {
        direction: "UP",
        confidence: "moderate",
        ratioLabel: label,
        biasLine: "CE unwinding at spot · sellers exiting",
        triggerLine: "Bullish if CE/PE drops below 1.0x",
        deltaLine,
      };
    }
    if (peBuilding) {
      return {
        direction: "CONFLICT",
        confidence: "weak",
        ratioLabel: label,
        biasLine: "CE dominant but PE building · tug of war at spot",
        triggerLine: "CE/PE must stay above 1.1x to keep bearish bias",
        deltaLine,
      };
    }
    return {
      direction: "DOWN",
      confidence: strength,
      ratioLabel: label,
      biasLine: "CE dominant at spot · sellers in control",
      triggerLine: "Bias flips bullish if CE/PE drops below 1.0x",
      deltaLine,
    };
  }

  if (ceBuilding && peBuilding) {
    return {
      direction: "CONFLICT",
      confidence: "weak",
      ratioLabel: label,
      biasLine: "Both sides building at spot · compression",
      triggerLine: "Wait — whichever stops building first loses",
      deltaLine,
    };
  }
  if (ceBuilding) {
    return {
      direction: "DOWN",
      confidence: "weak",
      ratioLabel: label,
      biasLine: "CE adding at balanced spot · sellers probing",
      triggerLine: "Watch CE/PE rise above 1.1x to confirm bearish",
      deltaLine,
    };
  }
  if (peBuilding) {
    return {
      direction: "UP",
      confidence: "weak",
      ratioLabel: label,
      biasLine: "PE adding at balanced spot · buyers probing",
      triggerLine: "Watch CE/PE drop below 0.9x to confirm bullish",
      deltaLine,
    };
  }
  return {
    direction: "FLAT",
    confidence: "weak",
    ratioLabel: label,
    biasLine: "Balanced at spot · no pressure from either side",
    triggerLine: "Wait for CE/PE to diverge from 1.0x",
    deltaLine,
  };
}

const resolveMagnetSub = (
  magnet: number | null | undefined,
  spot: number,
  strikeGap: number,
  magnetInterpretation: string | null | undefined,
  magnetCharacter: string | null | undefined,
): string | null => {
  if (typeof magnet !== "number" || !Number.isFinite(magnet)) return null;
  const interpretationText = String(magnetInterpretation || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ");
  if (interpretationText) return interpretationText;
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
  magnetInterpretation,
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

  const rubberBandActive = aboveR || belowS;
  const brokenLevel = aboveR ? resistance : belowS ? support : null;
  const tensionPx =
    rubberBandActive && brokenLevel !== null ? Math.abs(spot - brokenLevel) : 0;
  const tensionScale = Math.max(50, strikeGap * 2);
  const tension = clamp(tensionPx / tensionScale, 0, 1);

  // Rubber-band geometry v2 — honest outside-band dot position.
  const dangerExtMaxPct = 30;
  const dangerExtWidthPct = rubberBandActive
    ? clamp(tension * dangerExtMaxPct, 4, dangerExtMaxPct)
    : 0;
  const srRailWidthPct = 100 - (rubberBandActive ? dangerExtWidthPct : 0);

  const combinedPct = (value: number): number => {
    if (!rubberBandActive) {
      return clamp(((value - support) / bandWidth) * 100, 2, 98);
    }
    if (belowS) {
      const srPct = clamp(((value - support) / bandWidth) * srRailWidthPct, 0, srRailWidthPct);
      return dangerExtWidthPct + srPct;
    }
    const srPct = clamp(((value - support) / bandWidth) * srRailWidthPct, 0, srRailWidthPct);
    return srPct;
  };

  const dotCombinedPct: number = rubberBandActive
    ? belowS
      ? clamp(dangerExtWidthPct * (1 - tension) * 0.95, 2, Math.max(3, dangerExtWidthPct - 1))
      : clamp(srRailWidthPct + dangerExtWidthPct * tension * 0.95, srRailWidthPct + 1, 98)
    : combinedPct(spot);

  const snapPct: number | null = rubberBandActive
    ? belowS
      ? dangerExtWidthPct
      : srRailWidthPct
    : null;

  const supportPct = combinedPct(support);
  const resistancePct = combinedPct(resistance);
  const spotPct = rubberBandActive
    ? dotCombinedPct
    : clamp(((spot - support) / bandWidth) * 100, 2, 98);
  const prevResistancePct =
    typeof previousResistance === "number" ? combinedPct(previousResistance) : null;
  const peWallPct = typeof peWall === "number" ? combinedPct(peWall) : null;
  const ceWallPct = typeof ceWall === "number" ? combinedPct(ceWall) : null;
  const magnetPct = typeof magnet === "number" ? combinedPct(magnet) : null;
  const maxPainPct = typeof maxPain === "number" ? combinedPct(maxPain) : null;
  const overRFillWidthPct = 0;

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

  const strikePressureMap = useMemo(() => {
    const map: Record<number, StrikePressure> = {};
    for (const s of ladderStrikes) {
      map[s.strike] = computeStrikePressure(s.oi_ce || 0, s.oi_pe || 0);
    }
    return map;
  }, [ladderStrikes]);

  const spotZoneTriggers = useMemo(() => {
    const result: Record<number, TriggerHint> = {};
    if (spotStrikeForLadder == null) return result;
    const minus1 = spotStrikeForLadder - strikeGap;
    const plus1 = spotStrikeForLadder + strikeGap;
    for (const s of ladderStrikes) {
      if (s.strike === minus1 || s.strike === spotStrikeForLadder || s.strike === plus1) {
        result[s.strike] = resolveSpotTrigger(
          s.strike, spot, spotStrikeForLadder, s.oi_ce, s.oi_pe, s.oi_ce_change, s.oi_pe_change, strikeGap,
        );
      }
    }
    return result;
  }, [ladderStrikes, spotStrikeForLadder, strikeGap, spot]);

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
      below ? (strikePressureMap[below.strike] ?? null) : null,
      center ? (strikePressureMap[center.strike] ?? null) : null,
      above ? (strikePressureMap[above.strike] ?? null) : null,
    );
  }, [ladderStrikes, spotStrikeForLadder, strikePressureMap]);

  const nextMoveToneClass =
    nextMove.bias === "UP"
      ? "sbb-next-bias--up"
      : nextMove.bias === "DOWN"
        ? "sbb-next-bias--down"
        : nextMove.bias === "PINNED"
          ? "sbb-next-bias--pinned"
          : "sbb-next-bias--no_edge";
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
  void spotArrow;

  const topLabelStyle = (
    markerPct: number,
    color: string,
  ): Record<string, string | number> => {
    if (markerPct >= 94)
      return { right: "0px", left: "auto", transform: "none", color };
    if (markerPct <= 6) return { left: "0px", transform: "none", color };
    return { left: `${markerPct}%`, color };
  };

  const magnetMaxPainSame =
    typeof magnet === "number" &&
    typeof maxPain === "number" &&
    Math.round(magnet) === Math.round(maxPain);

  const magnetMaxPainClose =
    magnetPct !== null &&
    maxPainPct !== null &&
    !magnetMaxPainSame &&
    Math.abs(magnetPct - maxPainPct) < 4;

  const belowLabelStyle = (
    markerPct: number,
    color: string,
    stackIndex = 0,
  ): Record<string, string | number> => {
    const baseBottom = -16 - stackIndex * 13;
    if (markerPct >= 94) {
      return {
        right: `${stackIndex * 44}px`,
        left: "auto",
        transform: "none",
        color,
        bottom: `${baseBottom}px`,
      };
    }
    if (markerPct <= 6) {
      return {
        left: `${stackIndex * 44}px`,
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
          <div className={`sbb-rubber-v2${rejectionRisk ? " sbb-rubber-v2-risk" : ""}${materialBreachConfirmed ? " sbb-rubber-v2-accept" : ""}`}>
            <span className="sbb-rubber-v2-state">
              {aboveR ? "Above R" : "Below S"}
            </span>
            <span className="sbb-rubber-v2-distance">
              {Math.abs(Math.round(aboveR ? spot - resistance : support - spot))} pts
            </span>
            <span className="sbb-rubber-v2-tension">
              tension {Math.round(tension * 100)}%
            </span>
            {materialBreachConfirmed ? (
              <span className="sbb-rubber-v2-badge sbb-rubber-v2-badge-accept">Acceptance</span>
            ) : rejectionRisk ? (
              <span className="sbb-rubber-v2-badge sbb-rubber-v2-badge-reject">Rejection risk</span>
            ) : (
              <span className="sbb-rubber-v2-badge sbb-rubber-v2-badge-watch">Watch for snap</span>
            )}
          </div>
        ) : null}
        <div className="band-outer sbb-track-wrap">
          {rubberBandActive ? (
            <div className="sbb-track-rb-wrap">
              {belowS ? (
                <>
                  <div
                    className="sbb-track-rb-danger"
                    style={{
                      width: `${dangerExtWidthPct}%`,
                      opacity: 0.4 + tension * 0.5,
                    }}
                  />
                  <div
                    className="sbb-track-rb-sr"
                    style={{ width: `${srRailWidthPct}%`, opacity: 0.45 }}
                  />
                </>
              ) : (
                <>
                  <div
                    className="sbb-track-rb-sr"
                    style={{ width: `${srRailWidthPct}%`, opacity: 0.45 }}
                  />
                  <div
                    className="sbb-track-rb-danger"
                    style={{
                      width: `${dangerExtWidthPct}%`,
                      opacity: 0.4 + tension * 0.5,
                    }}
                  />
                </>
              )}
            </div>
          ) : (
            <div className="band-track sbb-track" />
          )}
          {rubberBandActive && snapPct !== null ? (
            <>
              <div
                className="sbb-snap-v2-marker"
                style={{
                  left: `${snapPct}%`,
                  boxShadow:
                    tension >= 0.6
                      ? `0 0 ${6 + tension * 8}px rgba(239,83,80,0.7)`
                      : undefined,
                }}
                aria-hidden="true"
              />
              <div
                className="sbb-snap-v2-label"
                style={{ left: `${snapPct}%` }}
              >
                {belowS ? `S ${fmt(support)}` : `R ${fmt(resistance)}`}
              </div>
              <div
                className={`sbb-tether-v2 sbb-tether-v2-${belowS ? "left" : "right"}`}
                style={{
                  left: belowS ? `${dotCombinedPct}%` : `${snapPct}%`,
                  width: belowS
                    ? `${snapPct - dotCombinedPct}%`
                    : `${dotCombinedPct - snapPct}%`,
                  opacity: 0.25 + tension * 0.5,
                }}
                aria-hidden="true"
              />
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
          {maxPainPct !== null && !magnetMaxPainSame ? (
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
              left: `${rubberBandActive ? dotCombinedPct : spotPct}%`,
              boxShadow: rubberBandActive
                ? `0 0 ${10 + tension * 14}px rgba(${aboveR ? "239,83,80" : "38,166,154"},${haloOpacity})${rejectionRisk ? ", 0 0 0 4px rgba(239,83,80,0.25), 0 0 0 8px rgba(239,83,80,0.12)" : ""}`
                : undefined,
            }}
          />
          {/* Suppress level label for the broken side — snap-v2-label already shows it */}
          {!belowS ? (
            <div className="sbb-lbl-above" style={topLabelStyle(supportPct, "#26a69a")}>
              S {fmt(support)}
            </div>
          ) : null}
          {!aboveR ? (
            <div className="sbb-lbl-above" style={topLabelStyle(resistancePct, "#ef5350")}>
              R {fmt(resistance)}
            </div>
          ) : null}
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
              {magnetMaxPainSame ? "magnet = max pain" : "magnet"}
            </div>
          ) : null}
          {maxPainPct !== null && !magnetMaxPainSame ? (
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
          <span className="sbb-next-bias-arrow">{nextMoveSymbol}</span>
          <span className="sbb-next-bias-dir">{nextMove.bias}</span>
          {nextMove.bias !== "NO_EDGE" ? (
            <span className="sbb-next-bias-conf">{nextMove.confidence}%</span>
          ) : null}
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
            const sub = resolveMagnetSub(
              magnet,
              spot,
              strikeGap,
              magnetInterpretation,
              magnetCharacter,
            );
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
            const pressure = strikePressureMap[s.strike];
            const isSpot = spotStrikeForLadder === s.strike;
            const isSpotMinus1 = spotStrikeForLadder != null && s.strike === spotStrikeForLadder - strikeGap;
            const isSpotPlus1 = spotStrikeForLadder != null && s.strike === spotStrikeForLadder + strikeGap;
            const isSpotZone = isSpot || isSpotMinus1 || isSpotPlus1;
            const trigger = spotZoneTriggers[s.strike] ?? null;
            const triggerCssDir = trigger
              ? trigger.direction === "UP" ? "bull"
                : trigger.direction === "DOWN" ? "bear"
                : "neutral"
              : null;
            const triggerDirClass = triggerCssDir ? ` sbb-trigger-${triggerCssDir}` : "";
            const hasWallTag =
              s.tag === "pe_wall" || s.tag === "ce_wall" || s.tag === "magnet" || s.tag === "maxpain";
            const showArrow = Boolean(
              pressure &&
              pressure.state !== "balanced" &&
              !hasWallTag,
            );
            const arrowUp =
              pressure?.state === "strong_support" ||
              pressure?.state === "support";
            return (
              <div
                key={s.strike}
                className={`sbb-strike-cell${isSpot ? " sbb-strike-cell-spot" : ""}${isSpotZone ? " sbb-strike-cell-focus" : " sbb-strike-cell-context"}${hasWallTag ? ` sbb-strike-cell-${s.tag}` : ""}${triggerDirClass}`}
              >
                {showArrow ? (
                  <span
                    className={`sbb-pressure-arrow sbb-pressure-arrow-${pressure?.state}`}
                    title={
                      pressure?.state === "strong_support"
                        ? "Strong support pressure"
                        : pressure?.state === "support"
                          ? "Support pressure"
                          : pressure?.state === "strong_resistance"
                            ? "Strong resistance pressure"
                            : "Resistance pressure"
                    }
                    aria-hidden="true"
                  >
                    {arrowUp ? "▲" : "▼"}
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
                {isSpotZone && trigger ? (
                  <div className={`sbb-trigger sbb-trigger-${triggerCssDir ?? "neutral"}`}>
                    <span className="sbb-trigger-ratio">{trigger.ratioLabel}</span>
                    <span className="sbb-trigger-cond">{trigger.biasLine}</span>
                    <span className="sbb-trigger-cond sbb-trigger-hint">{trigger.triggerLine}</span>
                    {trigger.deltaLine ? (
                      <span className="sbb-trigger-delta">{trigger.deltaLine}</span>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* legend removed in v2 - wall tags self-document */}
    </div>
  );
}
