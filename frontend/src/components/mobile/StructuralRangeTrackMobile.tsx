type StructuralRangeTrackMobileProps = {
  support: number | null;
  resistance: number | null;
  spot: number | null;
};

function formatLevel(value: number | null, digits = 0) {
  return typeof value === "number"
    ? value.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : "-";
}

export default function StructuralRangeTrackMobile({
  support,
  resistance,
  spot,
}: StructuralRangeTrackMobileProps) {
  const hasBand =
    typeof support === "number" &&
    typeof resistance === "number" &&
    typeof spot === "number" &&
    resistance > support;

  const bandWidth = hasBand ? resistance - support : 0;
  const position = hasBand ? Math.max(0, Math.min(100, ((spot - support) / bandWidth) * 100)) : 0;
  const supportSide = hasBand ? Math.max(0, Math.min(100, position)) : 0;
  const resistanceSide = hasBand ? Math.max(0, 100 - supportSide) : 100;
  const distToSupport = hasBand ? Math.round(spot - support) : null;
  const distToResistance = hasBand ? Math.round(resistance - spot) : null;

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-3">
      <div className="mb-1 grid grid-cols-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500">Support</span>
          <strong className="font-mono text-[15px] font-medium text-emerald-300">{formatLevel(support)}</strong>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[10px] text-slate-500">Spot</span>
          <strong className="font-mono text-[15px] font-medium text-slate-100">{formatLevel(spot, 1)}</strong>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-[10px] text-slate-500">Resistance</span>
          <strong className="font-mono text-[15px] font-medium text-rose-300">{formatLevel(resistance)}</strong>
        </div>
      </div>

      <div className="relative my-2 h-1.5 rounded-full bg-white/10">
        <div
          className="absolute left-0 top-0 h-full rounded-l-full bg-emerald-400/60"
          style={{ width: `${supportSide}%` }}
        />
        <div
          className="absolute right-0 top-0 h-full rounded-r-full bg-rose-400/45"
          style={{ width: `${resistanceSide}%` }}
        />
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-sky-400 bg-[#111e2c] shadow-[0_0_0_3px_rgba(91,164,232,0.15)]"
          style={{ left: `${position}%` }}
        />
      </div>

      <div className="flex justify-between gap-3 text-[10px] text-slate-500">
        <span>{hasBand ? `${Math.round(position)}% in band` : "Band unavailable"}</span>
        <span>{distToSupport !== null ? `${distToSupport} pts above support` : "-"}</span>
        <span>{distToResistance !== null ? `${distToResistance} pts below R` : "-"}</span>
      </div>
    </section>
  );
}
