type SpotHeroCardProps = {
  symbol: string;
  expiry: string | null;
  spot: number | null;
  spotChange: string;
  openChange: string;
  pctChange: string;
  updatedAt: string;
  regime: string;
  projection: string;
  dayTrend: string;
  longTrend: string;
  sessionPhase: string;
};

function formatSpotParts(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return { whole: "-", decimal: "" };
  }
  const text = value.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const [whole, decimal] = text.split(".");
  return { whole, decimal: decimal ? `.${decimal}` : "" };
}

function signedText(value: string, pct: string) {
  if (!value || value === "-") return pct || "-";
  return `${value.replace("+", "▲ ").replace("-", "▼ ")} ${pct}`.replace("  ", " ").trim();
}

function pillTone(kind: "neutral" | "up" | "phase") {
  if (kind === "up") return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";
  if (kind === "phase") return "border-amber-300/20 bg-amber-300/10 text-amber-200";
  return "border-white/8 bg-white/[0.04] text-slate-400";
}

export default function SpotHeroCard({
  symbol,
  expiry,
  spot,
  spotChange,
  openChange,
  pctChange,
  updatedAt,
  regime,
  projection,
  dayTrend,
  longTrend,
  sessionPhase,
}: SpotHeroCardProps) {
  const spotParts = formatSpotParts(spot);

  return (
    <section className="px-4 pb-1 pt-3">
      <div className="mb-1 text-[10px] font-medium tracking-[0.08em] text-slate-600">
        {symbol} {expiry ? `· ${expiry}` : ""}
      </div>

      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-[32px] font-light leading-none text-slate-100">
            {spotParts.whole}
            <sup className="text-base text-slate-500">{spotParts.decimal}</sup>
          </div>
          <div className="mt-1 text-[10px] text-slate-600">Updated {updatedAt || "-"}</div>
        </div>
        <div className="text-right">
          <div className="text-[14px] font-medium text-emerald-300">{signedText(spotChange, pctChange)}</div>
          <div className="mt-0.5 text-[10px] text-slate-500">
            from open {openChange ? openChange.replace("+", "▲ ").replace("-", "▼ ") : "-"}
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <div className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${pillTone("neutral")}`}>
          <span className="opacity-60">Regime</span>
          <span>{regime || "-"}</span>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${pillTone("neutral")}`}>
          <span className="opacity-60">Proj.</span>
          <span>{projection || "-"}</span>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${pillTone("up")}`}>
          <span className="opacity-60">Day</span>
          <span>{dayTrend || "-"}</span>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${pillTone("up")}`}>
          <span className="opacity-60">Long</span>
          <span>{longTrend || "-"}</span>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${pillTone("phase")}`}>
          <span className="opacity-60">Phase</span>
          <span>{sessionPhase || "-"}</span>
        </div>
      </div>
    </section>
  );
}
