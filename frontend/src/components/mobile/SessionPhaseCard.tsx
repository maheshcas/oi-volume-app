type SessionPhaseCardProps = {
  sessionPhase: string;
  regime: string;
  pressureState: string;
  readinessActive: boolean | null;
};

export default function SessionPhaseCard(props: SessionPhaseCardProps) {
  return (
    <section className="mx-4 flex items-center justify-between rounded-[12px] border border-violet-400/20 bg-violet-400/5 px-4 py-3">
      <div className="flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Session Phase</span>
        <span className="font-mono text-sm font-medium text-violet-300">{props.sessionPhase || "-"}</span>
      </div>
      <div className="flex flex-col items-end gap-1">
        <span className="text-[10px] text-slate-500">Regime</span>
        <span className="font-mono text-[13px] text-slate-200">{props.regime || "-"}</span>
        {props.readinessActive !== null ? (
          <span className={`font-mono text-[10px] ${props.readinessActive ? "text-emerald-300" : "text-slate-400"}`}>
            {props.readinessActive ? "Ready" : "Standby"} · {props.pressureState || "-"}
          </span>
        ) : null}
      </div>
    </section>
  );
}
