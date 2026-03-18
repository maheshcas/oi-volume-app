type KeyLevelsCardProps = {
  support: number | null;
  resistance: number | null;
  bullishTrigger: string | null;
  bearishTrigger: string | null;
  breakoutUp: number | null;
  breakoutDown: number | null;
};

function formatLevel(value: number | null) {
  return typeof value === "number" ? value.toLocaleString("en-IN") : "-";
}

function stateLabel(value: number | null) {
  if (typeof value !== "number") return "-";
  if (value >= 60) return "High";
  if (value >= 30) return "Moderate";
  return "Low";
}

export default function KeyLevelsCard({
  support,
  resistance,
  bullishTrigger,
  bearishTrigger,
  breakoutUp,
  breakoutDown,
}: KeyLevelsCardProps) {
  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-3 text-[10px] font-medium uppercase tracking-[0.07em] text-slate-600">Key levels</div>
      <div className="mb-2 grid grid-cols-2 gap-1.5">
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3">
          <div className="mb-1 text-[10px] text-slate-600">Active support</div>
          <div className="font-mono text-[15px] font-medium text-emerald-300">{formatLevel(support)}</div>
        </div>
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3">
          <div className="mb-1 text-[10px] text-slate-600">Active resistance</div>
          <div className="font-mono text-[15px] font-medium text-rose-300">{formatLevel(resistance)}</div>
        </div>
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3">
          <div className="mb-1 text-[10px] text-slate-600">Breakout trigger</div>
          <div className="font-mono text-[15px] font-medium text-sky-300">{bullishTrigger || "-"}</div>
        </div>
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3">
          <div className="mb-1 text-[10px] text-slate-600">Bear trigger</div>
          <div className="font-mono text-[15px] font-medium text-rose-300">{bearishTrigger || "-"}</div>
        </div>
      </div>

      <div className="mb-2 h-px bg-white/8" />

      <div className="flex gap-1.5">
        <div className="flex-1 rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3 text-center">
          <span className="mb-0.5 block font-mono text-[15px] font-medium text-rose-300">
            {typeof breakoutDown === "number" ? `${Math.round(breakoutDown)}%` : "-"}
          </span>
          <span className="text-[10px] text-slate-600">Down ({stateLabel(breakoutDown)})</span>
        </div>
        <div className="flex-1 rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3 text-center">
          <span className="mb-0.5 block font-mono text-[15px] font-medium text-emerald-300">
            {typeof breakoutUp === "number" ? `${Math.round(breakoutUp)}%` : "-"}
          </span>
          <span className="text-[10px] text-slate-600">Up ({stateLabel(breakoutUp)})</span>
        </div>
      </div>
    </section>
  );
}
