type AbsorptionAlertCardProps = {
  absorptionLevel: number | null;
  absorptionMessage: string | null;
  supportTransitionActive: boolean;
};

export default function AbsorptionAlertCard(props: AbsorptionAlertCardProps) {
  return (
    <section className="mx-4 rounded-[12px] border border-amber-300/20 bg-amber-300/6 px-4 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.08em] text-amber-200/80">Absorption Alert</div>
        {props.supportTransitionActive ? (
          <div className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 font-mono text-[11px] text-cyan-200">
            Support Shift
          </div>
        ) : null}
      </div>
      <p className="text-sm leading-6 text-amber-50">
        {props.absorptionMessage || "Absorption behavior is active near the defended support zone."}
      </p>
      <div className="mt-3 rounded-lg border border-white/10 bg-slate-950/40 px-3 py-3">
        <div className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Absorption Level</div>
        <div className="mt-1 font-mono text-base text-amber-100">
          {typeof props.absorptionLevel === "number" ? props.absorptionLevel.toLocaleString("en-IN") : "-"}
        </div>
      </div>
    </section>
  );
}
