type PrimarySignalCardProps = {
  tradeAction: string;
  resolvedReason: string;
  bias: string;
  readinessScore: number | null;
  readinessState: string;
  pressureState: string;
  regime: string;
};

function signalTone(action: string) {
  const text = action.toLowerCase();
  if (text.includes("long") || text.includes("bull")) return "border-emerald-400/25 bg-emerald-400/10 text-emerald-300";
  if (text.includes("short") || text.includes("bear")) return "border-rose-400/25 bg-rose-400/10 text-rose-300";
  return "border-amber-300/25 bg-amber-300/10 text-amber-200";
}

function readinessTone(state: string) {
  const text = state.toLowerCase();
  if (text.includes("high") || text.includes("active")) return "text-emerald-300";
  if (text.includes("low")) return "text-rose-300";
  return "text-amber-200";
}

export default function PrimarySignalCard(props: PrimarySignalCardProps) {
  const readiness = typeof props.readinessScore === "number" ? Math.max(0, Math.min(100, props.readinessScore)) : 0;

  return (
    <section className="mx-4 overflow-hidden rounded-[12px] border border-white/12 bg-[#0d1520]">
      <div className="flex items-center justify-between border-b border-white/7 px-4 py-3">
        <div className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Trade Signal</div>
        <div className={`rounded-md border px-3 py-1 font-mono text-xs font-semibold ${signalTone(props.tradeAction)}`}>
          {props.tradeAction || "WAIT"}
        </div>
      </div>

      <div className="px-4 py-4">
        <p className="mb-4 text-base font-medium leading-7 text-slate-100">
          {props.resolvedReason || "Waiting for directional confirmation from structure, pressure, and trap filters."}
        </p>

        <div className="mb-3">
          <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
            <span>Trade Readiness</span>
            <span className={`font-mono text-sm ${readinessTone(props.readinessState)}`}>
              {typeof props.readinessScore === "number" ? `${Math.round(props.readinessScore)}%` : "-"}
            </span>
          </div>
          <div className="relative h-1.5 rounded bg-white/6">
            <div
              className="h-1.5 rounded bg-gradient-to-r from-sky-400 to-emerald-300 transition-all"
              style={{ width: `${readiness}%` }}
            />
            <div className="absolute left-[57%] top-[-3px] h-3 w-0.5 rounded bg-amber-300" />
            <div className="absolute left-[57%] top-[-18px] -translate-x-1/2 font-mono text-[9px] text-amber-300">
              57 entry
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-[#111c2b] px-3 py-3">
            <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Bias</div>
            <div className="font-mono text-[13px] font-medium text-slate-100">{props.bias || "-"}</div>
          </div>
          <div className="rounded-lg bg-[#111c2b] px-3 py-3">
            <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Pressure</div>
            <div className="font-mono text-[13px] font-medium text-slate-100">{props.pressureState || "-"}</div>
          </div>
          <div className="rounded-lg bg-[#111c2b] px-3 py-3">
            <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Regime</div>
            <div className="font-mono text-[11px] font-medium text-slate-100">{props.regime || "-"}</div>
          </div>
          <div className="rounded-lg bg-[#111c2b] px-3 py-3">
            <div className="mb-1 text-[10px] uppercase tracking-[0.05em] text-slate-500">Readiness State</div>
            <div className={`font-mono text-[11px] font-medium ${readinessTone(props.readinessState)}`}>
              {props.readinessState || "-"}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
