import { AnimatePresence, motion } from "framer-motion";

type StructureBandProps = {
  support: number;
  resistance: number;
  spot: number;
  previousSupport?: number;
  previousResistance?: number;
  supportBroken: boolean;
  resistanceBroken: boolean;
  isNearSupport?: boolean;
  isNearResistance?: boolean;
  materialBreachConfirmed?: boolean;
  confirmationType?: string | null;
  trapDirection?: "upside" | "downside" | "" | null;
  trapAffectedLevel?: number | null;
  trapProbability?: number;
  embedded?: boolean;
  className?: string;
};

export type SPCState =
  | "WITHIN_STRUCTURE"
  | "SUPPORT_DEFENSE"
  | "RESISTANCE_PRESSURE"
  | "BREAKOUT_ATTEMPT"
  | "BREAKDOWN_ATTEMPT"
  | "CONFIRMED_EXPANSION";

type RangeBounds = {
  rangeMin: number;
  rangeMax: number;
  buffer: number;
};

const WIDE_SPREAD_THRESHOLD = 600;
const WIDE_SPREAD_HALF_WINDOW_CAP = 400;

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const formatLevel = (value: number) =>
  value.toLocaleString("en-IN", { maximumFractionDigits: 0 });

export function resolveSPCState(params: {
  spot: number;
  support: number;
  resistance: number;
  isNearSupport: boolean;
  isNearResistance: boolean;
  supportBroken: boolean;
  resistanceBroken: boolean;
  materialBreachConfirmed?: boolean;
  confirmationType?: string | null;
}): SPCState {
  const {
    supportBroken,
    resistanceBroken,
    isNearSupport,
    isNearResistance,
    materialBreachConfirmed,
  } = params;

  if (materialBreachConfirmed) {
    return "CONFIRMED_EXPANSION";
  }
  if (supportBroken && !resistanceBroken) {
    return "BREAKDOWN_ATTEMPT";
  }
  if (resistanceBroken && !supportBroken) {
    return "BREAKOUT_ATTEMPT";
  }
  if (isNearSupport) {
    return "SUPPORT_DEFENSE";
  }
  if (isNearResistance) {
    return "RESISTANCE_PRESSURE";
  }
  return "WITHIN_STRUCTURE";
}

export function isTrapDominant(trapProbability?: number) {
  if (typeof trapProbability !== "number" || !Number.isFinite(trapProbability)) {
    return false;
  }
  return trapProbability >= 55;
}

export function getSPCStateLabel(state: SPCState) {
  switch (state) {
    case "SUPPORT_DEFENSE":
      return "Support Holding";
    case "RESISTANCE_PRESSURE":
      return "Resistance Under Pressure";
    case "BREAKOUT_ATTEMPT":
      return "Breakout Attempt";
    case "BREAKDOWN_ATTEMPT":
      return "Breakdown Attempt";
    case "CONFIRMED_EXPANSION":
      return "Expansion Confirmed";
    default:
      return "Within Structure";
  }
}

export function getRangeBounds(params: {
  spot: number;
  support: number;
  resistance: number;
  previousSupport?: number;
  previousResistance?: number;
}): RangeBounds {
  const { spot, support, resistance } = params;
  const spread = Math.max(1, resistance - support);
  const buffer = clamp(spread * 0.08, 20, 60);
  const supportOverflow = Math.max(0, support - spot);
  const resistanceOverflow = Math.max(0, spot - resistance);

  if (spread <= WIDE_SPREAD_THRESHOLD) {
    const leftBreachPadding =
      supportOverflow > 0 ? clamp(buffer + supportOverflow * 1.5, 30, 90) : buffer;
    const rightBreachPadding =
      resistanceOverflow > 0 ? clamp(buffer + resistanceOverflow * 1.5, 30, 90) : buffer;

    return {
      rangeMin: Math.min(support - buffer, spot - leftBreachPadding),
      rangeMax: Math.max(resistance + buffer, spot + rightBreachPadding),
      buffer,
    };
  }

  const halfWindow = Math.min(spread * 0.5, WIDE_SPREAD_HALF_WINDOW_CAP) + buffer;
  const centeredMin = spot - halfWindow;
  const centeredMax = spot + halfWindow;

  return {
    rangeMin: Math.min(centeredMin, support - buffer),
    rangeMax: Math.max(centeredMax, resistance + buffer),
    buffer,
  };
}

export function normalizePosition(value: number, rangeMin: number, rangeMax: number) {
  if (!Number.isFinite(value) || !Number.isFinite(rangeMin) || !Number.isFinite(rangeMax) || rangeMax <= rangeMin) {
    return 0;
  }
  return clamp(((value - rangeMin) / (rangeMax - rangeMin)) * 100, 0, 100);
}

type OrbState = "normal" | "support" | "resistance" | "breakdown" | "breakout";

function getOrbState(state: SPCState, params: {
  safeSupportBroken: boolean;
  safeResistanceBroken: boolean;
}): OrbState {
  if (state === "SUPPORT_DEFENSE") return "support";
  if (state === "RESISTANCE_PRESSURE") return "resistance";
  if (state === "BREAKDOWN_ATTEMPT") return "breakdown";
  if (state === "BREAKOUT_ATTEMPT") return "breakout";
  if (state === "CONFIRMED_EXPANSION") {
    if (params.safeSupportBroken) return "breakdown";
    if (params.safeResistanceBroken) return "breakout";
  }
  return "normal";
}

function getOrbTheme(state: OrbState) {
  switch (state) {
    case "support":
      return {
        core: "#34d399",
        coreGlow: "rgba(52,211,153,0.6)",
        glow: "0 0 10px rgba(52,211,153,0.92), 0 0 28px rgba(52,211,153,0.48)",
        halo: "rgba(52,211,153,0.28)",
      };
    case "resistance":
      return {
        core: "#f87171",
        coreGlow: "rgba(248,113,113,0.6)",
        glow: "0 0 10px rgba(248,113,113,0.92), 0 0 28px rgba(248,113,113,0.48)",
        halo: "rgba(248,113,113,0.28)",
      };
    case "breakdown":
      return {
        core: "#ef4444",
        coreGlow: "rgba(239,68,68,0.62)",
        glow: "0 0 12px rgba(239,68,68,0.95), 0 0 30px rgba(239,68,68,0.52)",
        halo: "rgba(239,68,68,0.3)",
      };
    case "breakout":
      return {
        core: "#f59e0b",
        coreGlow: "rgba(245,158,11,0.62)",
        glow: "0 0 12px rgba(245,158,11,0.95), 0 0 30px rgba(245,158,11,0.52)",
        halo: "rgba(245,158,11,0.3)",
      };
    default:
      return {
        core: "#38bdf8",
        coreGlow: "rgba(59,130,246,0.6)",
        glow: "0 0 10px rgba(56,189,248,0.92), 0 0 26px rgba(56,189,248,0.44)",
        halo: "rgba(56,189,248,0.26)",
      };
  }
}

function getLabelOffset(levelPos: number, spotPos: number, preference: "left" | "right") {
  if (Math.abs(levelPos - spotPos) < 5) {
    return preference === "left" ? -48 : 48;
  }
  return 0;
}

function getTrapZone(params: {
  trapDirection?: "upside" | "downside" | "" | null;
  trapAffectedLevel?: number | null;
  support: number;
  resistance: number;
  spot: number;
  bandWidth: number;
  bandWidthPct: number;
  rangeMin: number;
  rangeMax: number;
  trapProbability?: number;
}) {
  const {
    trapDirection,
    trapAffectedLevel,
    support,
    resistance,
    spot,
    bandWidth,
    bandWidthPct,
    rangeMin,
    rangeMax,
    trapProbability,
  } = params;

  if (!trapDirection) return null;

  const anchor =
    typeof trapAffectedLevel === "number"
      ? trapAffectedLevel
      : trapDirection === "downside"
        ? resistance
        : support;

  const center = normalizePosition(anchor, rangeMin, rangeMax);
  const intensityBase = clamp(1 - Math.abs(spot - anchor) / Math.max(1, bandWidth), 0.2, 1);
  const probabilityFactor =
    typeof trapProbability === "number" ? clamp(trapProbability / 100, 0.35, 1) : 0.7;

  return {
    center,
    width: clamp(bandWidthPct * 0.18, 6, 14),
    opacity: clamp(0.18 + intensityBase * 0.32 * probabilityFactor, 0.18, 0.56),
    sideClass: trapDirection === "downside" ? "sb-trap-downside" : "sb-trap-upside",
  };
}

function PreviousMarker({
  left,
  label,
  offsetX,
}: {
  left: number;
  label: string;
  offsetX: number;
}) {
  return (
    <motion.div
      className="sb-prev-marker"
      style={{ left: `${left}%` }}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
    >
      <div className="sb-prev-tick" />
      {offsetX !== 0 ? (
        <div
          className="sb-prev-leader"
          style={{
            width: `${Math.abs(offsetX)}px`,
            left: offsetX > 0 ? "0px" : `${offsetX}px`,
          }}
        />
      ) : null}
      <div className="sb-prev-pill" style={{ marginLeft: `${offsetX}px` }}>
        {label}
      </div>
    </motion.div>
  );
}

export default function StructureBand({
  support,
  resistance,
  spot,
  previousSupport,
  previousResistance,
  supportBroken,
  resistanceBroken,
  isNearSupport = false,
  isNearResistance = false,
  materialBreachConfirmed,
  confirmationType,
  trapDirection = null,
  trapAffectedLevel = null,
  trapProbability,
  embedded = false,
  className = "",
}: StructureBandProps) {
  const safeSupportBroken = supportBroken && !resistanceBroken;
  const safeResistanceBroken = resistanceBroken && !supportBroken;
  const spcState = resolveSPCState({
    spot,
    support,
    resistance,
    isNearSupport,
    isNearResistance,
    supportBroken: safeSupportBroken,
    resistanceBroken: safeResistanceBroken,
    materialBreachConfirmed,
    confirmationType,
  });
  const orbState = getOrbState(spcState, {
    safeSupportBroken,
    safeResistanceBroken,
  });
  const orbTheme = getOrbTheme(orbState);
  const trapDominant = isTrapDominant(trapProbability);
  const stateLabel = getSPCStateLabel(spcState);
  const showSafeBadge = !trapDominant && (typeof trapProbability !== "number" || trapProbability <= 10);

  const { rangeMin, rangeMax } = getRangeBounds({
    spot,
    support,
    resistance,
    previousSupport,
    previousResistance,
  });

  const supportPos = normalizePosition(support, rangeMin, rangeMax);
  const resistancePos = normalizePosition(resistance, rangeMin, rangeMax);
  const spotPos = normalizePosition(spot, rangeMin, rangeMax);
  const prevSupportPos =
    typeof previousSupport === "number"
      ? normalizePosition(previousSupport, rangeMin, rangeMax)
      : null;
  const prevResistancePos =
    typeof previousResistance === "number"
      ? normalizePosition(previousResistance, rangeMin, rangeMax)
      : null;

  const bandLeft = Math.min(supportPos, resistancePos);
  const bandRight = Math.max(supportPos, resistancePos);
  const bandWidthPct = Math.max(0, bandRight - bandLeft);
  const bandWidth = Math.max(1, resistance - support);
  const supportEdgePct = clamp((spot - support) / bandWidth, 0, 1);
  const resistanceEdgePct = clamp((resistance - spot) / bandWidth, 0, 1);
  const defendedWidth = bandWidthPct * 0.22;
  const activeWidth = bandWidthPct * 0.56;
  const resistanceWidth = Math.max(0, bandWidthPct - defendedWidth - activeWidth);

  const showLeftExtension =
    spcState === "BREAKDOWN_ATTEMPT" ||
    (spcState === "CONFIRMED_EXPANSION" && safeSupportBroken);
  const showRightExtension =
    spcState === "BREAKOUT_ATTEMPT" ||
    (spcState === "CONFIRMED_EXPANSION" && safeResistanceBroken);
  const leftExtensionRaw = showLeftExtension ? Math.max(0, bandLeft - spotPos) : 0;
  const rightExtensionRaw = showRightExtension ? Math.max(0, spotPos - bandRight) : 0;
  const maxExtension = bandWidthPct * 0.5;
  const leftExtension = Math.min(leftExtensionRaw, maxExtension);
  const rightExtension = Math.min(rightExtensionRaw, maxExtension);

  const showPrevSupport =
    typeof previousSupport === "number" &&
    Math.abs(previousSupport - support) > 0.001 &&
    prevSupportPos !== null;
  const showPrevResistance =
    typeof previousResistance === "number" &&
    Math.abs(previousResistance - resistance) > 0.001 &&
    prevResistancePos !== null;

  const prevSupportOffset =
    showPrevSupport && prevSupportPos !== null
      ? getLabelOffset(prevSupportPos, spotPos, "left")
      : 0;
  const prevResistanceOffset =
    showPrevResistance && prevResistancePos !== null
      ? getLabelOffset(prevResistancePos, spotPos, "right")
      : 0;

  const trapZone = trapDominant
    ? getTrapZone({
        trapDirection,
        trapAffectedLevel,
        support,
        resistance,
        spot,
        bandWidth,
        bandWidthPct,
        rangeMin,
        rangeMax,
        trapProbability,
      })
    : null;

  const supportShiftWidth =
    showPrevSupport && prevSupportPos !== null
      ? Math.min(Math.abs(supportPos - prevSupportPos), bandWidthPct * 0.35)
      : 0;
  const supportShiftLeft =
    showPrevSupport && prevSupportPos !== null
      ? Math.min(prevSupportPos, supportPos)
      : 0;
  const resistanceShiftWidth =
    showPrevResistance && prevResistancePos !== null
      ? Math.min(Math.abs(prevResistancePos - resistancePos), bandWidthPct * 0.35)
      : 0;
  const resistanceShiftLeft =
    showPrevResistance && prevResistancePos !== null
      ? Math.min(prevResistancePos, resistancePos)
      : 0;
  const preSupportTension =
    spcState === "WITHIN_STRUCTURE" && !isNearSupport && supportEdgePct <= 0.1;
  const preResistanceTension =
    spcState === "WITHIN_STRUCTURE" && !isNearResistance && resistanceEdgePct <= 0.1;

  const containerClass = ["sb-container", embedded ? "sb-embedded" : "", className]
    .filter(Boolean)
    .join(" ");

  const orbMotion =
    spcState === "SUPPORT_DEFENSE"
      ? {
          y: [0, -0.5, 0],
          transition: { duration: 1.8, repeat: Infinity, ease: "easeInOut" as const },
        }
      : spcState === "RESISTANCE_PRESSURE"
        ? {
            scale: [1, 1.015, 1],
            transition: { duration: 1.3, repeat: Infinity, ease: "easeInOut" as const },
          }
        : spcState === "BREAKDOWN_ATTEMPT"
          ? { scaleX: [1, 1.04, 1], transition: { duration: 0.55, ease: "easeOut" as const } }
          : spcState === "BREAKOUT_ATTEMPT"
            ? { scaleX: [1, 1.05, 1], transition: { duration: 0.55, ease: "easeOut" as const } }
            : {};

  const haloLoop =
    spcState === "SUPPORT_DEFENSE"
      ? { scale: [1, 1.08, 1], opacity: [0.8, 0.95, 0.8], transition: { duration: 1.9, repeat: Infinity, ease: "easeInOut" as const } }
      : spcState === "RESISTANCE_PRESSURE"
        ? { scale: [1, 1.05, 1], opacity: [0.82, 0.94, 0.82], transition: { duration: 1.35, repeat: Infinity, ease: "easeInOut" as const } }
        : spcState === "CONFIRMED_EXPANSION"
          ? { scale: 1, opacity: 0.88, transition: { duration: 0.22, ease: "easeOut" as const } }
        : { scale: [1, 1.04, 1], opacity: [0.76, 0.88, 0.76], transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" as const } };

  return (
    <div className={containerClass}>
      {!embedded ? <div className="sb-state-chip">{stateLabel}</div> : null}
      {!embedded ? (
        <div className="sb-zone-row">
          <div className="sb-zone-chip sb-zone-chip-support">Support</div>
          <div className="sb-zone-chip sb-zone-chip-active">Active</div>
          <div className="sb-zone-chip sb-zone-chip-resistance">Resistance</div>
        </div>
      ) : null}

      <div className="sb-rail-wrap">
        {showSafeBadge ? (
          <div className="sb-left-badge">SAFE</div>
        ) : null}
        <div className="sb-base-rail" />
        <div className="sb-base-highlight" />

        {showPrevSupport && supportShiftWidth > 0 ? (
          <motion.div
            className="sb-memory-segment"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.45, left: `${supportShiftLeft}%`, width: `${supportShiftWidth}%` }}
            transition={{ duration: 0.24, ease: "easeOut" }}
          />
        ) : null}

        {showPrevResistance && resistanceShiftWidth > 0 ? (
          <motion.div
            className="sb-memory-segment"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.45, left: `${resistanceShiftLeft}%`, width: `${resistanceShiftWidth}%` }}
            transition={{ duration: 0.24, ease: "easeOut" }}
          />
        ) : null}

        <motion.div
          className="sb-band-shell"
          initial={{ opacity: 0, scaleY: 0.92 }}
          animate={{ opacity: 1, scaleY: 1, left: `${bandLeft}%`, width: `${bandWidthPct}%` }}
          transition={{ duration: 0.28, ease: "easeOut" }}
        />
        <motion.div
          className="sb-band-glow"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.92, left: `${bandLeft}%`, width: `${bandWidthPct}%` }}
          transition={{ duration: 0.32, ease: "easeOut" }}
        />

        <motion.div
          className={`sb-segment sb-segment-support ${isNearSupport ? "sb-segment-tension-support" : preSupportTension ? "sb-segment-pre-tension-support" : ""}`}
          animate={{ left: `${bandLeft}%`, width: `${defendedWidth}%` }}
          transition={{ duration: 0.26, ease: "easeOut" }}
        />
        <motion.div
          className="sb-segment sb-segment-active"
          animate={{ left: `${bandLeft + defendedWidth}%`, width: `${activeWidth}%` }}
          transition={{ duration: 0.26, ease: "easeOut" }}
        />
        <motion.div
          className={`sb-segment sb-segment-resistance ${isNearResistance ? "sb-segment-tension-resistance" : preResistanceTension ? "sb-segment-pre-tension-resistance" : ""}`}
          animate={{ left: `${bandLeft + defendedWidth + activeWidth}%`, width: `${resistanceWidth}%` }}
          transition={{ duration: 0.26, ease: "easeOut" }}
        />
        <motion.div
          className="sb-band-shine"
          animate={{ left: `${bandLeft}%`, width: `${bandWidthPct}%` }}
          transition={{ duration: 0.26, ease: "easeOut" }}
        />

        <AnimatePresence initial={false}>
          {showLeftExtension && leftExtension > 0 ? (
            <motion.div
              key="sb-extension-left"
              className="sb-extension sb-extension-left"
              initial={{ opacity: 0, width: 0, left: `${bandLeft}%` }}
              animate={{ opacity: 1, width: `${leftExtension}%`, left: `${bandLeft - leftExtension}%` }}
              exit={{ opacity: 0, width: 0, left: `${bandLeft}%` }}
              transition={{ duration: 0.22, ease: "easeOut" }}
            />
          ) : null}
          {showRightExtension && rightExtension > 0 ? (
            <motion.div
              key="sb-extension-right"
              className="sb-extension sb-extension-right"
              initial={{ opacity: 0, width: 0, left: `${bandRight}%` }}
              animate={{ opacity: 1, width: `${rightExtension}%`, left: `${bandRight}%` }}
              exit={{ opacity: 0, width: 0, left: `${bandRight}%` }}
              transition={{ duration: 0.22, ease: "easeOut" }}
            />
          ) : null}
        </AnimatePresence>

        {!embedded && (showLeftExtension || showRightExtension) ? (
          <motion.div
            className="sb-extension-chip"
            initial={{ opacity: 0, y: 4 }}
            animate={{
              opacity: 1,
              y: 0,
              left: `${
                showLeftExtension
                  ? bandLeft - leftExtension / 2
                  : bandRight + rightExtension / 2
              }%`,
            }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            Break Zone
          </motion.div>
        ) : null}

        <AnimatePresence initial={false}>
          {trapZone ? (
            <motion.div
              key={`${trapZone.sideClass}-${Math.round(trapZone.center * 10)}`}
              className={`sb-trap-zone ${trapZone.sideClass}`}
              initial={{ opacity: 0 }}
              animate={{
                left: `${trapZone.center}%`,
                width: `${trapZone.width}%`,
                opacity: [trapZone.opacity * 0.82, trapZone.opacity, trapZone.opacity * 0.82],
              }}
              exit={{ opacity: 0 }}
              transition={{
                left: { duration: 0.22, ease: "easeOut" },
                width: { duration: 0.22, ease: "easeOut" },
                opacity: { duration: 2.2, repeat: Infinity, ease: "easeInOut" },
              }}
            />
          ) : null}
        </AnimatePresence>

        <motion.div
          className="sb-edge sb-edge-support"
          animate={{
            left: `${supportPos}%`,
            opacity: spcState === "SUPPORT_DEFENSE" ? [0.75, 0.9, 0.75] : 0.85,
            scaleY: spcState === "SUPPORT_DEFENSE" ? [1, 1.04, 1] : 1,
          }}
          transition={{
            left: { duration: 0.26, ease: "easeOut" },
            opacity: { duration: 1.7, repeat: spcState === "SUPPORT_DEFENSE" ? Infinity : 0, ease: "easeInOut" },
            scaleY: { duration: 1.7, repeat: spcState === "SUPPORT_DEFENSE" ? Infinity : 0, ease: "easeInOut" },
          }}
        />
        <motion.div
          className="sb-edge sb-edge-resistance"
          animate={{
            left: `${resistancePos}%`,
            opacity: spcState === "RESISTANCE_PRESSURE" ? [0.75, 0.9, 0.75] : 0.85,
            scaleY: spcState === "RESISTANCE_PRESSURE" ? [1, 1.04, 1] : 1,
          }}
          transition={{
            left: { duration: 0.26, ease: "easeOut" },
            opacity: { duration: 1.45, repeat: spcState === "RESISTANCE_PRESSURE" ? Infinity : 0, ease: "easeInOut" },
            scaleY: { duration: 1.45, repeat: spcState === "RESISTANCE_PRESSURE" ? Infinity : 0, ease: "easeInOut" },
          }}
        />

        {showPrevSupport && prevSupportPos !== null ? (
          <PreviousMarker
            left={prevSupportPos}
            label={`Prev S ${formatLevel(previousSupport!)}`}
            offsetX={prevSupportOffset}
          />
        ) : null}

        {showPrevResistance && prevResistancePos !== null ? (
          <PreviousMarker
            left={prevResistancePos}
            label={`Prev R ${formatLevel(previousResistance!)}`}
            offsetX={prevResistanceOffset}
          />
        ) : null}

        <motion.div
          className="sb-spot-anchor"
          animate={{ left: `${spotPos}%` }}
          transition={{
            duration: safeSupportBroken || safeResistanceBroken ? 0.22 : 0.32,
            ease: safeSupportBroken || safeResistanceBroken ? [0.2, 0.8, 0.2, 1] : [0.25, 0.8, 0.25, 1],
          }}
        >
          {!embedded ? <div className="sb-spot-value">{formatLevel(spot)}</div> : null}
          <motion.div className="sb-orb" animate={orbMotion}>
            <motion.div
              className="sb-orb-halo"
              style={{
                backgroundColor: orbTheme.halo,
                boxShadow: `0 0 18px ${orbTheme.coreGlow}, 0 0 32px ${orbTheme.coreGlow}`,
              }}
              animate={haloLoop}
            />
            <motion.div
              className="sb-orb-glow"
              style={{
                backgroundColor: orbTheme.core,
                boxShadow: `0 0 6px rgba(255,255,255,0.9), 0 0 18px ${orbTheme.coreGlow}, 0 0 32px ${orbTheme.coreGlow}`,
              }}
              animate={{
                opacity:
                  spcState === "BREAKDOWN_ATTEMPT" || spcState === "BREAKOUT_ATTEMPT"
                    ? [0.38, 0.5, 0.38]
                    : spcState === "CONFIRMED_EXPANSION"
                      ? 0.46
                      : [0.34, 0.42, 0.34],
              }}
              transition={{
                duration: 1.7,
                repeat: spcState === "CONFIRMED_EXPANSION" ? 0 : Infinity,
                ease: "easeInOut",
              }}
            />
            <motion.div
              className="sb-orb-core"
              style={{
                background: `radial-gradient(circle at 35% 35%, rgba(255,255,255,0.98) 0%, rgba(255,255,255,0.88) 28%, ${orbTheme.core} 72%, ${orbTheme.core} 100%)`,
                boxShadow: `0 0 6px rgba(255,255,255,0.9), 0 0 18px ${orbTheme.coreGlow}, 0 0 32px ${orbTheme.coreGlow}`,
              }}
              whileHover={undefined}
              animate={{
                scale:
                  spcState === "BREAKDOWN_ATTEMPT" || spcState === "BREAKOUT_ATTEMPT"
                    ? [1, 1.03, 1]
                    : 1,
              }}
              transition={{
                duration: 0.9,
                repeat:
                  spcState === "BREAKDOWN_ATTEMPT" || spcState === "BREAKOUT_ATTEMPT"
                    ? Infinity
                    : 0,
                ease: "easeInOut",
              }}
            />
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
