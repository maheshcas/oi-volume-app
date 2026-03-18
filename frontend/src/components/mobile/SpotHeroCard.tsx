type SpotHeroCardProps = {
  symbol: string;
  spot: number | null;
  spotChange: string;
  openChange: string;
  pctChange: string;
  maxPain: string;
  pcr: string;
  updatedAt: string;
};

function formatSpot(value: number | null) {
  if (value === null || Number.isNaN(value)) return "-";
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function isNegative(text: string) {
  return text.trim().startsWith("-");
}

export default function SpotHeroCard(props: SpotHeroCardProps) {
  const changeText =
    props.spotChange && props.pctChange && props.spotChange !== "-" && props.pctChange !== "-"
      ? `${props.spotChange} ${props.pctChange}`
      : props.pctChange || props.spotChange || "-";
  const changeTone = isNegative(changeText)
    ? "bg-rose-400/12 text-rose-300"
    : "bg-emerald-400/12 text-emerald-300";

  return (
    <section className="border-b border-white/7 bg-[linear-gradient(135deg,rgba(0,200,255,0.04)_0%,transparent_60%)] px-4 py-4">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div className="font-mono text-[32px] font-semibold tracking-[-0.06em] text-slate-50">
          {formatSpot(props.spot)}
        </div>
        <div className={`rounded-md px-3 py-1 font-mono text-[13px] ${changeTone}`}>
          {changeText}
        </div>
      </div>
      <div className="flex flex-wrap gap-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-[0.05em] text-slate-500">Max Pain</span>
          <span className="font-mono text-[13px] font-medium text-slate-100">{props.maxPain}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-[0.05em] text-slate-500">PCR</span>
          <span className="font-mono text-[13px] font-medium text-slate-100">{props.pcr}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-[0.05em] text-slate-500">Updated</span>
          <span className="font-mono text-[11px] font-medium text-slate-500">{props.updatedAt || "-"}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-[0.05em] text-slate-500">From Open</span>
          <span className={`font-mono text-[13px] font-medium ${isNegative(props.openChange) ? "text-rose-300" : "text-emerald-300"}`}>
            {props.openChange || "-"}
          </span>
        </div>
      </div>
    </section>
  );
}
