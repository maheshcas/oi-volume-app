type DecisionGridMobileProps = {
  putWall: number | null;
  callWall: number | null;
  bullishTrigger: string | null;
  bearishTrigger: string | null;
};

function formatLevel(value: number | null) {
  return typeof value === "number" ? value.toLocaleString("en-IN") : "-";
}

export default function DecisionGridMobile(props: DecisionGridMobileProps) {
  return (
    <section>
      <div className="px-4 pb-2 text-[11px] uppercase tracking-[0.08em] text-slate-500">
        Decision Layer
      </div>
      <div className="grid grid-cols-2 gap-2 px-4">
        <div className="rounded-[10px] border border-white/8 bg-[#0d1520] p-3">
          <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Put Wall</div>
          <div className="font-mono text-[13px] font-medium text-slate-100">{formatLevel(props.putWall)}</div>
        </div>
        <div className="rounded-[10px] border border-white/8 bg-[#0d1520] p-3">
          <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Call Wall</div>
          <div className="font-mono text-[13px] font-medium text-slate-100">{formatLevel(props.callWall)}</div>
        </div>
        <div className="rounded-[10px] border border-white/8 bg-[#0d1520] p-3">
          <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Bull Trigger</div>
          <div className="font-mono text-[13px] font-medium text-emerald-300">{props.bullishTrigger || "-"}</div>
        </div>
        <div className="rounded-[10px] border border-white/8 bg-[#0d1520] p-3">
          <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Bear Trigger</div>
          <div className="font-mono text-[13px] font-medium text-rose-300">{props.bearishTrigger || "-"}</div>
        </div>
      </div>
    </section>
  );
}
