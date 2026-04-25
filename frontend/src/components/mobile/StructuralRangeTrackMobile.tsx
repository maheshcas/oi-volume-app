type StructuralRangeTrackMobileProps = {
  support: number | null;
  resistance: number | null;
  spot: number | null;
  previousResistance?: number | null;
  magnet?: number | null;
  magnetPullDirection?: string | null;
  magnetDistancePts?: number | null;
  magnetCharacter?: string | null;
};

function formatLevel(value: number | null, digits = 0) {
  return typeof value === "number"
    ? value.toLocaleString("en-IN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
    : "-";
}

function magnetArrow(direction?: string | null) {
  const d = String(direction || "").trim().toLowerCase();
  if (d === "up") return "▲";
  if (d === "down") return "▼";
  if (d === "at") return "◉";
  return "";
}

export default function StructuralRangeTrackMobile({
  support,
  resistance,
  spot,
  previousResistance,
  magnet,
  magnetPullDirection,
  magnetDistancePts,
  magnetCharacter,
}: StructuralRangeTrackMobileProps) {
  const hasBand =
    typeof support === "number" &&
    typeof resistance === "number" &&
    typeof spot === "number" &&
    resistance > support;

  const bandWidth = hasBand ? resistance! - support! : 0;

  function pct(value: number) {
    return Math.max(2, Math.min(98, ((value - support!) / bandWidth) * 100));
  }

  const spotPct = hasBand ? pct(spot!) : 50;
  const prevResPct =
    hasBand && typeof previousResistance === "number" ? pct(previousResistance) : null;
  const magnetPct = hasBand && typeof magnet === "number" ? pct(magnet) : null;

  const distToSupport = hasBand ? Math.round(spot! - support!) : null;
  const distToResistance = hasBand ? Math.round(resistance! - spot!) : null;
  const aboveR = hasBand && spot! > resistance!;
  const belowS = hasBand && spot! < support!;
  const outsideBand = aboveR || belowS;

  const tension = outsideBand && hasBand
    ? Math.min(
        1,
        Math.abs(belowS ? spot! - support! : spot! - resistance!) / bandWidth,
      )
    : 0;

  const snapPct = belowS ? 2 : aboveR ? 98 : null;

  const locationText = !hasBand
    ? "Band unavailable"
    : belowS
      ? `${Math.abs(distToSupport ?? 0)} pts below S`
      : aboveR
        ? `${Math.abs(distToResistance ?? 0)} pts above R`
        : `${Math.round(((spot! - support!) / bandWidth) * 100)}% in band`;

  const magnetLabel =
    typeof magnet === "number"
      ? `${formatLevel(magnet)} ${magnetArrow(magnetPullDirection)}${
          magnetDistancePts != null
            ? ` ${Math.round(magnetDistancePts)}pts`
            : ""
        }`
      : null;

  return (
    <section className="mx-3 mb-2 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-3">
      {/* Outside-band state badge */}
      {outsideBand ? (
        <div className={`mb-2 flex items-center gap-2 rounded-xl border px-3 py-2 text-[11px] font-medium ${
          aboveR
            ? "border-emerald-400/20 bg-emerald-400/6 text-emerald-300"
            : "border-rose-400/30 bg-rose-400/8 text-rose-300"
        }`}>
          <span className="text-[13px]">{belowS ? "↓" : "↑"}</span>
          <span>{belowS ? "Below support" : "Above resistance"}</span>
          <span className="ml-auto font-mono text-[10px] opacity-70">
            {Math.round(tension * 100)}% extended
          </span>
          <span className="rounded bg-white/8 px-1.5 py-0.5 text-[9px] uppercase tracking-wide">
            snap → {belowS ? formatLevel(support) : formatLevel(resistance)}
          </span>
        </div>
      ) : null}

      {/* Level row */}
      <div className="mb-1 grid grid-cols-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500">Support</span>
          <strong className={`font-mono text-[15px] font-medium ${
            belowS ? "text-rose-300" : "text-emerald-300"
          }`}>
            {formatLevel(support)}
          </strong>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[10px] text-slate-500">Spot</span>
          <strong className="font-mono text-[15px] font-medium text-slate-100">
            {formatLevel(spot, 1)}
          </strong>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-[10px] text-slate-500">Resistance</span>
          <strong className={`font-mono text-[15px] font-medium ${
            aboveR ? "text-emerald-300" : "text-rose-300"
          }`}>
            {formatLevel(resistance)}
          </strong>
        </div>
      </div>

      {/* Track */}
      <div className="relative my-2.5 h-2 rounded-full bg-white/8">
        {hasBand && !outsideBand ? (
          <>
            <div
              className="absolute left-0 top-0 h-full rounded-l-full bg-emerald-400/50"
              style={{ width: `${spotPct}%` }}
            />
            <div
              className="absolute right-0 top-0 h-full rounded-r-full bg-rose-400/35"
              style={{ width: `${100 - spotPct}%` }}
            />
          </>
        ) : outsideBand ? (
          <>
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background: belowS
                  ? "linear-gradient(90deg, rgba(239,83,80,0.7) 0%, rgba(239,83,80,0.15) 100%)"
                  : "linear-gradient(90deg, rgba(239,83,80,0.15) 0%, rgba(239,83,80,0.7) 100%)",
                opacity: 0.4 + tension * 0.5,
              }}
            />
            {snapPct !== null ? (
              <div
                className="absolute top-[-3px] h-[14px] w-[2px] rounded bg-white/70"
                style={{ left: `${snapPct}%`, transform: "translateX(-50%)" }}
              />
            ) : null}
          </>
        ) : null}

        {prevResPct !== null ? (
          <div
            className="absolute top-1/2 h-3 w-[2px] -translate-y-1/2 rounded"
            style={{ left: `${prevResPct}%`, background: "rgba(156,163,175,0.7)" }}
          />
        ) : null}

        {magnetPct !== null ? (
          <div
            className="absolute top-1/2 h-3.5 w-[2px] -translate-y-1/2 rounded"
            style={{ left: `${magnetPct}%`, background: "#f59e0b" }}
          />
        ) : null}

        {/* Spot dot */}
        <div
          className={`absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-[#111e2c] ${
            belowS
              ? "border-rose-400 shadow-[0_0_0_3px_rgba(239,83,80,0.15)]"
              : aboveR
                ? "border-emerald-400 shadow-[0_0_0_3px_rgba(52,211,153,0.15)]"
                : "border-sky-400 shadow-[0_0_0_3px_rgba(91,164,232,0.15)]"
          }`}
          style={{ left: `${spotPct}%` }}
        />
      </div>

      {/* Stats row */}
      <div className="flex justify-between gap-2 text-[10px] text-slate-500">
        <span className={outsideBand ? "font-medium text-rose-300" : ""}>
          {locationText}
        </span>
        {distToSupport !== null && !belowS ? (
          <span>{distToSupport} pts above S</span>
        ) : null}
        {distToResistance !== null && !aboveR ? (
          <span>{distToResistance} pts to R</span>
        ) : null}
      </div>

      {/* Magnet + prev resistance strip */}
      {magnetLabel || typeof previousResistance === "number" ? (
        <div className="mt-2 flex flex-wrap gap-2 border-t border-white/8 pt-2">
          {magnetLabel ? (
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              <span className="text-[10px] text-amber-300">
                Magnet {magnetLabel}
                {magnetCharacter ? (
                  <span className="ml-1 text-slate-500">
                    · {String(magnetCharacter).replace(/[_-]+/g, " ")}
                  </span>
                ) : null}
              </span>
            </div>
          ) : null}
          {typeof previousResistance === "number" ? (
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-400/70" />
              <span className="text-[10px] text-slate-400">
                Prev R {formatLevel(previousResistance)}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
