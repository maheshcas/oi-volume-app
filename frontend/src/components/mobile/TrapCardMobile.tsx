type TrapCardMobileProps = {
  trapProbability: number | null;
  trapType: string;
  trapDirection?: "upside" | "downside" | "";
  explanation: string;
  severity: "low" | "moderate" | "high";
  affectedLevel?: number | null;
  spot?: number | null;
  resistance?: number | null;
};

function severityTone(severity: TrapCardMobileProps["severity"]) {
  if (severity === "high") return "text-rose-300 border-rose-400/20 bg-rose-400/10";
  if (severity === "moderate") return "text-amber-200 border-amber-300/20 bg-amber-300/10";
  return "text-emerald-300 border-emerald-400/20 bg-emerald-400/10";
}

function severityBarClass(severity: TrapCardMobileProps["severity"]) {
  if (severity === "high") return "bg-rose-300";
  if (severity === "moderate") return "bg-amber-200";
  return "bg-emerald-300";
}

function severityValueClass(severity: TrapCardMobileProps["severity"]) {
  if (severity === "high") return "text-rose-300";
  if (severity === "moderate") return "text-amber-200";
  return "text-emerald-300";
}

function resolveDirectionalContext(
  direction: TrapCardMobileProps["trapDirection"],
  affectedLevel: number | null | undefined,
  spot: number | null | undefined,
  resistance: number | null | undefined,
  probability: number,
): { title: string; sub: string; tone: "up" | "down" | "flat" } | null {
  const hasSpot = typeof spot === "number" && Number.isFinite(spot);
  const hasR = typeof resistance === "number" && Number.isFinite(resistance);
  const aboveR = hasSpot && hasR && (spot as number) > (resistance as number);

  if (aboveR && probability < 50 && hasR) {
    return {
      title: `Breakout above ${(resistance as number).toLocaleString("en-IN")}`,
      sub: "Low trap risk · watch for acceptance",
      tone: "up",
    };
  }
  if (aboveR && probability >= 50 && hasR) {
    return {
      title: `False breakout risk above ${(resistance as number).toLocaleString("en-IN")}`,
      sub: `Trap ${probability}% · watch for reversal`,
      tone: "up",
    };
  }
  if (direction === "downside" && affectedLevel) {
    return {
      title: `Resistance rejection at ${Number(affectedLevel).toLocaleString("en-IN")}`,
      sub: "Watch for reversal back into range",
      tone: "down",
    };
  }
  if (direction === "upside" && affectedLevel) {
    return {
      title: `Support absorption at ${Number(affectedLevel).toLocaleString("en-IN")}`,
      sub: "Watch for bounce or breakdown follow-through",
      tone: "up",
    };
  }
  return null;
}

export default function TrapCardMobile({
  trapProbability,
  trapType,
  trapDirection,
  explanation,
  severity,
  affectedLevel,
  spot = null,
  resistance = null,
}: TrapCardMobileProps) {
  const progress =
    typeof trapProbability === "number"
      ? Math.max(0, Math.min(100, trapProbability))
      : 0;
  const tone = severityTone(severity);
  const probability = typeof trapProbability === "number" ? Math.round(trapProbability) : 0;
  const directional = resolveDirectionalContext(
    trapDirection,
    affectedLevel,
    spot,
    resistance,
    probability,
  );

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="text-[14px] font-medium text-slate-100">Trap risk</div>
        <div className={`rounded-full border px-3 py-1 text-[11px] font-medium ${tone}`}>
          {severity[0].toUpperCase() + severity.slice(1)}
        </div>
      </div>

      {/* Hero percentage + bar */}
      <div className="mb-1 flex items-end justify-between">
        <div className={`font-mono text-[28px] font-medium ${severityValueClass(severity)}`}>
          {typeof trapProbability === "number" ? `${probability}%` : "-"}
        </div>
        <div className="text-[11px] text-slate-500">false-break risk</div>
      </div>
      <div className="relative mb-1 h-[4px] rounded-full bg-white/8">
        <div
          className={`h-full rounded-full transition-all ${severityBarClass(severity)}`}
          style={{ width: `${progress}%` }}
        />
        {/* 55% gate tick */}
        <div className="absolute left-[55%] top-[-3px] h-[10px] w-[1px] rounded bg-white/35" />
      </div>
      <div className="mb-3 text-right text-[9px] text-slate-600">55% threshold</div>

      {/* Directional context block */}
      {directional ? (
        <div className={`mb-3 flex items-start gap-2.5 rounded-xl border px-3 py-2.5 ${
          directional.tone === "up"
            ? "border-rose-400/20 bg-rose-400/6"
            : directional.tone === "down"
              ? "border-emerald-400/20 bg-emerald-400/6"
              : "border-white/8 bg-white/[0.02]"
        }`}>
          <span className={`mt-0.5 shrink-0 text-[14px] ${
            directional.tone === "up" ? "text-rose-300" : "text-emerald-300"
          }`}>
            {directional.tone === "up" ? "↑" : "↓"}
          </span>
          <div className="min-w-0">
            <div className="text-[12px] font-semibold leading-5 text-slate-100">
              {directional.title}
            </div>
            <div className="text-[11px] leading-5 text-slate-400">
              {directional.sub}
            </div>
          </div>
        </div>
      ) : null}

      {/* Detail rows — removed "Risk level" duplicate */}
      <div className="space-y-0.5">
        <div className="flex items-center justify-between border-b border-white/8 py-1.5 text-[12px]">
          <span className="text-slate-500">Trap type</span>
          <span className="font-medium text-slate-100">{trapType || "No active trap"}</span>
        </div>
        <div className="flex items-center justify-between border-b border-white/8 py-1.5 text-[12px]">
          <span className="text-slate-500">Direction</span>
          <span className="font-medium text-slate-100">
            {trapDirection === "downside"
              ? "Resistance rejection"
              : trapDirection === "upside"
                ? "Support absorption"
                : "-"}
          </span>
        </div>
        <div className="flex items-center justify-between py-1.5 text-[12px]">
          <span className="text-slate-500">Affected level</span>
          <span className="font-mono font-medium text-slate-100">
            {typeof affectedLevel === "number"
              ? affectedLevel.toLocaleString("en-IN")
              : "-"}
          </span>
        </div>
      </div>

      {/* Suggested action */}
      <div className="mt-3 rounded-xl border border-amber-300/15 bg-amber-300/5 px-3 py-3">
        <div className="mb-1 text-[9px] uppercase tracking-[0.1em] text-amber-300/70">
          Recommended
        </div>
        <div className="text-[12px] leading-5 text-slate-300">{explanation}</div>
      </div>
    </section>
  );
}
