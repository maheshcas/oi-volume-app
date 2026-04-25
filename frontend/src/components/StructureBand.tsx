import { AnimatePresence, motion } from "framer-motion";

type StructureBandProps = {
  support: number;
  resistance: number;
  spot: number;

  previousSupport?: number | null;
  previousResistance?: number | null;

  supportBroken?: boolean;
  resistanceBroken?: boolean;

  nearSupport?: boolean;
  nearResistance?: boolean;

  embedded?: boolean;

  supportLabel?: string;
  resistanceLabel?: string;
  supportMeta?: string;
  resistanceMeta?: string;

  showReentryMarker?: boolean;
};

const cx = (...parts: Array<string | false | null | undefined>) =>
  parts.filter(Boolean).join(" ");

const clamp = (n: number, min: number, max: number) => Math.min(max, Math.max(min, n));

function getRangeBounds(
  support: number,
  resistance: number,
  spot: number,
  supportBroken: boolean,
  resistanceBroken: boolean,
) {
  void supportBroken;
  void resistanceBroken;
  const spread = Math.max(1, resistance - support);
  const buffer = Math.max(40, Math.round(spread * 0.08));

  if (spread <= 600) {
    return {
      min: support - buffer,
      max: resistance + buffer,
    };
  }

  const halfWindow = spread * 0.5 + buffer;
  const centeredMin = spot - halfWindow;
  const centeredMax = spot + halfWindow;

  return {
    min: Math.min(centeredMin, support - buffer),
    max: Math.max(centeredMax, resistance + buffer),
  };
}

function normalizePosition(value: number, min: number, max: number) {
  if (!Number.isFinite(value) || max <= min) return 50;
  return clamp(((value - min) / (max - min)) * 100, 0, 100);
}

function getPositionSummary({
  support,
  resistance,
  spot,
  supportBroken,
  resistanceBroken,
  nearSupport,
  nearResistance,
}: {
  support: number;
  resistance: number;
  spot: number;
  supportBroken: boolean;
  resistanceBroken: boolean;
  nearSupport: boolean;
  nearResistance: boolean;
}) {
  void support;
  void resistance;
  if (supportBroken) return "Below support";
  if (resistanceBroken) return "Above resistance";
  if (nearSupport) return "Close to support";
  if (nearResistance) return "Close to resistance";
  if (spot > support && spot < resistance) return "Inside band";
  return "At boundary";
}

function getOrbTone({
  supportBroken,
  resistanceBroken,
  nearSupport,
  nearResistance,
}: {
  supportBroken: boolean;
  resistanceBroken: boolean;
  nearSupport: boolean;
  nearResistance: boolean;
}) {
  if (supportBroken) return "breakdown";
  if (resistanceBroken) return "breakout";
  if (nearSupport) return "support";
  if (nearResistance) return "resistance";
  return "neutral";
}

export default function StructureBand({
  support,
  resistance,
  spot,
  previousSupport = null,
  previousResistance = null,
  supportBroken = false,
  resistanceBroken = false,
  nearSupport = false,
  nearResistance = false,
  embedded = false,
  supportLabel = "Defended Support",
  resistanceLabel = "Resistance Watch",
  supportMeta,
  resistanceMeta,
  showReentryMarker = true,
}: StructureBandProps) {
  const brokenS = Boolean(supportBroken) && spot < support;
  const brokenR = Boolean(resistanceBroken) && spot > resistance;

  const activeBrokenS = brokenS && !brokenR;
  const activeBrokenR = brokenR && !brokenS;

  const { min, max } = getRangeBounds(support, resistance, spot, activeBrokenS, activeBrokenR);

  const supportPct = normalizePosition(support, min, max);
  const resistancePct = normalizePosition(resistance, min, max);

  const prevSPct =
    previousSupport != null ? normalizePosition(previousSupport, min, max) : null;
  const prevRPct =
    previousResistance != null ? normalizePosition(previousResistance, min, max) : null;

  let spotPct = normalizePosition(spot, min, max);
  if (activeBrokenS) spotPct = Math.max(0, supportPct - 7);
  if (activeBrokenR) spotPct = Math.min(100, resistancePct + 7);

  const reentryPct = activeBrokenS ? supportPct : activeBrokenR ? resistancePct : null;

  const insideBand = !activeBrokenS && !activeBrokenR && spot > support && spot < resistance;

  const bandClass = cx(
    "sb-band",
    activeBrokenS && "sb-band--broken-support",
    activeBrokenR && "sb-band--broken-resistance",
    embedded && "sb-band--embedded",
    insideBand && "sb-band--stable",
  );

  const orbTone = getOrbTone({
    supportBroken: activeBrokenS,
    resistanceBroken: activeBrokenR,
    nearSupport,
    nearResistance,
  });

  const centerText = getPositionSummary({
    support,
    resistance,
    spot,
    supportBroken: activeBrokenS,
    resistanceBroken: activeBrokenR,
    nearSupport,
    nearResistance,
  });

  const breakdownInvalidationText = `Reclaim above ${support.toLocaleString("en-IN")} → breakdown invalid`;
  const breakoutInvalidationText = `Back below ${resistance.toLocaleString("en-IN")} → breakout invalid`;

  return (
    <div className="sb-shell">
      {!embedded ? (
        <div className="sb-topline">
          <div className="sb-col sb-col--left">
            <div className="sb-kicker">Support</div>
            <div className="sb-value sb-value--support">S {support.toLocaleString("en-IN")}</div>
            {supportMeta ? <div className="sb-meta">{supportMeta}</div> : null}
          </div>

          <div className="sb-col sb-col--center">
            <div className="sb-kicker">Spot</div>
            <div
              className={cx(
                "sb-value",
                "sb-value--spot",
                activeBrokenS && "sb-value--danger",
                activeBrokenR && "sb-value--warning",
              )}
            >
              {spot.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </div>
            <div className="sb-center-summary">{centerText}</div>
          </div>

          <div className="sb-col sb-col--right">
            <div className="sb-kicker">Resistance</div>
            <div className="sb-value sb-value--resistance">R {resistance.toLocaleString("en-IN")}</div>
            {resistanceMeta ? <div className="sb-meta">{resistanceMeta}</div> : null}
          </div>
        </div>
      ) : null}

      <AnimatePresence initial={false}>
        {activeBrokenS ? (
          <motion.div
            key="support-broken-banner"
            className="sb-event-banner sb-event-banner--down"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22 }}
          >
            <div className="sb-event-title">Support broken</div>
            <div className="sb-event-text">
              Breakdown active — watch continuation unless price reclaims support.
            </div>
          </motion.div>
        ) : null}

        {activeBrokenR ? (
          <motion.div
            key="resistance-broken-banner"
            className="sb-event-banner sb-event-banner--up"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22 }}
          >
            <div className="sb-event-title">Resistance broken</div>
            <div className="sb-event-text">
              Breakout active — watch continuation unless price falls back below resistance.
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="sb-band-wrap">
        <div className="sb-band-clip">
          <div className="sb-band-effects" />
          <div className={bandClass}>
            <div className="sb-rail-base" />

            <motion.div
              className={cx("sb-rail-main", (activeBrokenS || activeBrokenR) && "sb-rail-main--dimmed")}
              style={{
                left: `${supportPct}%`,
                width: `${Math.max(0, resistancePct - supportPct)}%`,
              }}
              animate={{
                opacity: activeBrokenS || activeBrokenR ? 0.42 : 1,
              }}
              transition={{ duration: 0.25 }}
            />

            <div className="sb-level-pin sb-level-pin--support" style={{ left: `${supportPct}%` }} />
            <div className="sb-level-pin sb-level-pin--resistance" style={{ left: `${resistancePct}%` }} />

            {prevSPct != null ? (
              <div className="sb-prev-group" style={{ left: `${prevSPct}%` }}>
                <div className="sb-prev-tick" />
                {!embedded ? (
                  <div className="sb-prev-pill">Prev S {previousSupport?.toLocaleString("en-IN")}</div>
                ) : null}
              </div>
            ) : null}

            {prevRPct != null ? (
              <div className="sb-prev-group" style={{ left: `${prevRPct}%` }}>
                <div className="sb-prev-tick" />
                {!embedded ? (
                  <div className="sb-prev-pill">Prev R {previousResistance?.toLocaleString("en-IN")}</div>
                ) : null}
              </div>
            ) : null}

            <AnimatePresence initial={false}>
              {activeBrokenS ? (
                <motion.div
                  key="left-breach"
                  className="sb-breach sb-breach--left"
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ width: `${Math.min(18, supportPct)}%`, opacity: 1 }}
                  exit={{ width: 0, opacity: 0 }}
                  transition={{ duration: 0.28, ease: "easeOut" }}
                  style={{ right: `${100 - supportPct}%` }}
                />
              ) : null}

              {activeBrokenR ? (
                <motion.div
                  key="right-breach"
                  className="sb-breach sb-breach--right"
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ width: `${Math.min(18, 100 - resistancePct)}%`, opacity: 1 }}
                  exit={{ width: 0, opacity: 0 }}
                  transition={{ duration: 0.28, ease: "easeOut" }}
                  style={{ left: `${resistancePct}%` }}
                />
              ) : null}
            </AnimatePresence>

            <AnimatePresence initial={false}>
              {showReentryMarker && reentryPct != null ? (
                <motion.div
                  key="reentry-marker"
                  className="sb-reentry"
                  style={{ left: `${reentryPct}%` }}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.22 }}
                >
                  <div className="sb-reentry-tick" />
                  {!embedded ? (
                    <div className="sb-reentry-label">
                      {activeBrokenS ? breakdownInvalidationText : breakoutInvalidationText}
                    </div>
                  ) : null}
                </motion.div>
              ) : null}
            </AnimatePresence>

            <motion.div
              className={cx("sb-orb", `sb-orb--${orbTone}`)}
              style={{ left: `${spotPct}%` }}
              animate={{
                scale: activeBrokenS || activeBrokenR ? 1.04 : 1,
              }}
              transition={{ duration: 0.22 }}
            >
              <div className="sb-orb-halo" />
              <div className="sb-orb-mid" />
              <div className="sb-orb-core" />
            </motion.div>
          </div>
        </div>
      </div>

      {!embedded ? (
        <div className="sb-zone-row">
          <div className="sb-zone-pill sb-zone-pill--support">
            {activeBrokenS ? "Broken support" : supportLabel}
          </div>
          <div className="sb-zone-pill sb-zone-pill--center">
            {activeBrokenS ? "Breakdown active" : activeBrokenR ? "Breakout active" : "Active zone"}
          </div>
          <div className="sb-zone-pill sb-zone-pill--resistance">
            {activeBrokenR ? "Broken resistance" : resistanceLabel}
          </div>
        </div>
      ) : null}
    </div>
  );
}
