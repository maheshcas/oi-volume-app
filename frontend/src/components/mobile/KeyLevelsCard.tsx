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

export default function KeyLevelsCard(props: KeyLevelsCardProps) {
  return (
    <section className="mx-4 overflow-hidden rounded-[12px] border border-white/7 bg-[#0d1520]">
      <div className="border-b border-white/7 px-4 py-3 text-[11px] uppercase tracking-[0.08em] text-slate-500">Key Levels</div>
      <div className="px-4 py-3">
        <div className="flex items-center justify-between border-b border-white/7 py-3">
          <span className="text-sm text-slate-500">Active Support</span>
          <span className="font-mono text-[15px] font-semibold text-emerald-300">{formatLevel(props.support)}</span>
        </div>
        <div className="flex items-center justify-between border-b border-white/7 py-3">
          <span className="text-sm text-slate-500">Active Resistance</span>
          <span className="font-mono text-[15px] font-semibold text-rose-300">{formatLevel(props.resistance)}</span>
        </div>
        <div className="flex items-center justify-between border-b border-white/7 py-3">
          <span className="text-sm text-slate-500">Breakout Trigger</span>
          <span className="font-mono text-[15px] font-semibold text-sky-300">{props.bullishTrigger || "-"}</span>
        </div>
        <div className="flex items-center justify-between py-3">
          <span className="text-sm text-slate-500">Bear Trigger</span>
          <span className="font-mono text-[15px] font-semibold text-rose-300">{props.bearishTrigger || "-"}</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-[#111c2b] px-3 py-3">
            <div className="mb-1 text-[10px] text-slate-500">Downside prob</div>
            <div className="font-mono text-lg font-semibold text-rose-300">
              {typeof props.breakoutDown === "number" ? `${Math.round(props.breakoutDown)}%` : "-"}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">Risk state</div>
          </div>
          <div className="rounded-lg bg-[#111c2b] px-3 py-3">
            <div className="mb-1 text-[10px] text-slate-500">Upside prob</div>
            <div className="font-mono text-lg font-semibold text-emerald-300">
              {typeof props.breakoutUp === "number" ? `${Math.round(props.breakoutUp)}%` : "-"}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">Risk state</div>
          </div>
        </div>
      </div>
    </section>
  );
}
