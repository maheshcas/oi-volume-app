type TradePlanMobileProps = {
  tradeAction: string;
  bullishTrigger: string | null;
  bearishTrigger: string | null;
  support: number | null;
  resistance: number | null;
};

function planTitle(action: string) {
  const text = action.toLowerCase();
  if (text.includes("long")) return "Look for continuation, not late chase.";
  if (text.includes("short")) return "Breakdown needs clean confirmation.";
  return "Avoid breakout trades.";
}

export default function TradePlanMobile({
  tradeAction,
  bullishTrigger,
  bearishTrigger,
  support,
  resistance,
}: TradePlanMobileProps) {
  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-3 text-[10px] font-medium uppercase tracking-[0.07em] text-slate-500">Trade plan</div>
      <div className="mb-3 text-[20px] font-medium leading-7 text-slate-100">{planTitle(tradeAction)}</div>

      <div className="flex gap-3 border-b border-white/8 py-2 text-[12px]">
        <span className="min-w-[58px] pt-0.5 text-[11px] font-medium text-emerald-300">Bullish</span>
        <span className="text-slate-400">
          {bullishTrigger ?? (typeof resistance === "number" ? `Acceptance above ${resistance.toLocaleString("en-IN")}` : "-")}
        </span>
      </div>
      <div className="flex gap-3 border-b border-white/8 py-2 text-[12px]">
        <span className="min-w-[58px] pt-0.5 text-[11px] font-medium text-rose-300">Bearish</span>
        <span className="text-slate-400">
          {bearishTrigger ?? (typeof support === "number" ? `Break below ${support.toLocaleString("en-IN")}` : "-")}
        </span>
      </div>
      <div className="flex gap-3 py-2 text-[12px]">
        <span className="min-w-[58px] pt-0.5 text-[11px] font-medium text-slate-500">Invalid</span>
        <span className="text-slate-400">Range compression breaks</span>
      </div>
    </section>
  );
}
