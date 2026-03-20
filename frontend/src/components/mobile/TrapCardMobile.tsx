type TrapCardMobileProps = {
  trapProbability: number | null;
  trapType: string;
  trapDirection?: "upside" | "downside" | "";
  explanation: string;
  severity: "low" | "moderate" | "high";
  affectedLevel?: number | null;
};

function severityTone(severity: TrapCardMobileProps["severity"]) {
  if (severity === "high") return "text-rose-300 border-rose-400/20 bg-rose-400/10";
  if (severity === "moderate") return "text-amber-200 border-amber-300/20 bg-amber-300/10";
  return "text-emerald-300 border-emerald-400/20 bg-emerald-400/10";
}

function directionPill(direction: TrapCardMobileProps["trapDirection"]) {
  if (direction === "upside") {
    return (
      <span className="dir-pill dp-absorption">
        <span className="dir-arrow">↓</span>
        <span>Support absorption</span>
      </span>
    );
  }
  if (direction === "downside") {
    return (
      <span className="dir-pill dp-rejection">
        <span className="dir-arrow">↑</span>
        <span>Resistance rejection</span>
      </span>
    );
  }
  return <span className="text-slate-500">-</span>;
}

export default function TrapCardMobile({
  trapProbability,
  trapType,
  trapDirection,
  explanation,
  severity,
  affectedLevel,
}: TrapCardMobileProps) {
  const progress = typeof trapProbability === "number" ? Math.max(0, Math.min(100, trapProbability)) : 0;
  const tone = severityTone(severity);

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-[14px] font-medium text-slate-100">Trap risk</div>
        <div className={`rounded-full border px-3 py-1 text-[11px] font-medium ${tone}`}>
          {severity[0].toUpperCase() + severity.slice(1)}
        </div>
      </div>

      <div className="mb-1 flex items-end justify-between">
        <div className="text-[12px] text-slate-500">Trap risk %</div>
        <div className={`font-mono text-[28px] font-medium ${severity === "high" ? "text-rose-300" : severity === "moderate" ? "text-amber-200" : "text-emerald-300"}`}>
          {typeof trapProbability === "number" ? `${Math.round(trapProbability)}%` : "-"}
        </div>
      </div>
      <div className="mb-3 h-1 rounded-full bg-white/8">
        <div
          className={`h-full rounded-full ${severity === "high" ? "bg-rose-300" : severity === "moderate" ? "bg-amber-200" : "bg-emerald-300"}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="space-y-0.5">
        <div className="flex items-center justify-between border-b border-white/8 py-1.5 text-[12px]">
          <span className="text-slate-500">Risk level</span>
          <span className={severity === "high" ? "text-rose-300" : severity === "moderate" ? "text-amber-200" : "text-emerald-300"}>
            {severity[0].toUpperCase() + severity.slice(1)}
          </span>
        </div>
        <div className="flex items-center justify-between border-b border-white/8 py-1.5 text-[12px]">
          <span className="text-slate-500">Trap type</span>
          <span className="font-medium text-slate-100">{trapType || "No active trap"}</span>
        </div>
        <div className="flex items-center justify-between border-b border-white/8 py-1.5 text-[12px]">
          <span className="text-slate-500">Direction</span>
          {directionPill(trapDirection)}
        </div>
        <div className="flex items-center justify-between py-1.5 text-[12px]">
          <span className="text-slate-500">Affected level</span>
          <span className="font-mono font-medium text-slate-100">
            {typeof affectedLevel === "number" ? affectedLevel.toLocaleString("en-IN") : "-"}
          </span>
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-3">
        <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-slate-600">Suggested action</div>
        <div className="text-[12px] leading-6 text-slate-400">{explanation}</div>
      </div>
    </section>
  );
}
