type TrapCardMobileProps = {
  trapProbability: number | null;
  trapType: string;
  explanation: string;
  severity: "low" | "moderate" | "high";
};

const severityClass: Record<TrapCardMobileProps["severity"], string> = {
  low: "border-sky-400/15 bg-sky-400/8 text-sky-200",
  moderate: "border-amber-300/20 bg-amber-300/8 text-amber-200",
  high: "border-rose-400/20 bg-rose-400/8 text-rose-200",
};

export default function TrapCardMobile(props: TrapCardMobileProps) {
  const progress = typeof props.trapProbability === "number" ? Math.max(0, Math.min(100, props.trapProbability)) : 0;

  return (
    <section className={`mx-4 rounded-[12px] border px-4 py-4 ${severityClass[props.severity]}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.08em] text-current/75">Trap Risk</div>
        <div className="font-mono text-2xl font-semibold">
          {typeof props.trapProbability === "number" ? `${Math.round(props.trapProbability)}%` : "-"}
        </div>
      </div>
      <div className="mb-3 h-1 rounded-full bg-white/8">
        <div className="h-1 rounded-full bg-current transition-all" style={{ width: `${progress}%` }} />
      </div>
      <div className="flex items-center justify-between gap-3">
        <div className="font-mono text-sm">{props.trapType || "No active trap"}</div>
        <div className="rounded-full border border-current/20 px-2.5 py-1 text-[11px] uppercase tracking-[0.18em]">
          {props.severity}
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{props.explanation}</p>
    </section>
  );
}
