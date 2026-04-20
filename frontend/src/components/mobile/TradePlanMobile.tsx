import type { MobileEntryTarget } from "./types";

type TradePlanMobileProps = {
  tradeAction: string;
  bullishTrigger: string | null;
  bearishTrigger: string | null;
  support: number | null;
  resistance: number | null;
  entryTarget?: MobileEntryTarget | null;
};

function fmt(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "-";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function fmtPremium(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return null;
  return `₹${v.toFixed(1)}`;
}

function badgeClass(action?: string | null, optType?: string | null) {
  const a = String(action || "").toUpperCase();
  const o = String(optType || "").toUpperCase();
  if (o === "STRADDLE") return "border-violet-400/30 bg-violet-400/10 text-violet-300";
  if (a === "BUY" && o === "CE") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-300";
  if (a === "BUY" && o === "PE") return "border-rose-400/30 bg-rose-400/10 text-rose-300";
  if (a === "SELL") return "border-amber-300/30 bg-amber-300/10 text-amber-200";
  return "border-white/10 bg-white/[0.04] text-slate-400";
}

function badgeLabel(action?: string | null, optType?: string | null) {
  const a = String(action || "").toUpperCase();
  const o = String(optType || "").toUpperCase();
  if (o === "STRADDLE") return "STRADDLE";
  if (a && o) return `${a} ${o}`;
  if (a) return a;
  return "TRADE";
}

function magnetArrow(direction?: string | null) {
  const d = String(direction || "").trim().toLowerCase();
  if (d === "up") return "▲";
  if (d === "down") return "▼";
  if (d === "at") return "◉";
  return "";
}

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
  entryTarget,
}: TradePlanMobileProps) {
  const tradeType = String(entryTarget?.trade_type || "NONE").toUpperCase();
  const hasSetup = tradeType !== "NONE" && entryTarget != null;

  if (!hasSetup) {
    return (
      <section className="mx-3 mb-2 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
        <div className="mb-3 text-[10px] font-medium uppercase tracking-[0.07em] text-slate-500">Trade plan</div>
        <div className="mb-3 text-[18px] font-medium leading-7 text-slate-100">{planTitle(tradeAction)}</div>

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

        {entryTarget?.price_magnet_strike ? (
          <div className="mt-3 flex items-center gap-2 border-t border-white/8 pt-3 text-[11px]">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
            <span className="text-amber-300">
              Magnet {fmt(entryTarget.price_magnet_strike)}
              {magnetArrow(entryTarget.magnet_pull_direction) ? ` ${magnetArrow(entryTarget.magnet_pull_direction)}` : ""}
              {entryTarget.magnet_distance_pts != null ? ` ${Math.round(entryTarget.magnet_distance_pts)}pts` : ""}
            </span>
          </div>
        ) : null}
      </section>
    );
  }

  const badge = badgeLabel(entryTarget.entry_option_action, entryTarget.entry_option_type);
  const bClass = badgeClass(entryTarget.entry_option_action, entryTarget.entry_option_type);
  const stopPremium = fmtPremium(entryTarget.stop_premium_value);
  const magArrow = magnetArrow(entryTarget.magnet_pull_direction);
  const magnetConflict =
    String(entryTarget.entry_option_action || "").toUpperCase() === "SELL" &&
    String(entryTarget.entry_option_type || "").toUpperCase() === "CE" &&
    String(entryTarget.magnet_pull_direction || "").toLowerCase() === "up";

  return (
    <section className="mx-3 mb-2 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-[0.07em] text-slate-500">Trade Setup</span>
        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${bClass}`}>{badge}</span>
      </div>

      {/* Brief */}
      {entryTarget.entry_brief ? (
        <div className="mb-3 text-[12px] leading-5 text-slate-300">{entryTarget.entry_brief}</div>
      ) : null}

      {/* Entry/Stop/T1/T2 grid */}
      <div className="mb-3 grid grid-cols-2 gap-1.5">
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2">
          <div className="mb-0.5 text-[10px] text-slate-500">Entry</div>
          <div className="font-mono text-[13px] font-medium text-slate-100">
            {fmt(entryTarget.entry_underlying)}
          </div>
          {entryTarget.entry_option_strike ? (
            <div className="mt-0.5 text-[10px] text-slate-500">
              {entryTarget.entry_option_type} {fmt(entryTarget.entry_option_strike)}
              {entryTarget.entry_premium != null ? ` · ₹${entryTarget.entry_premium.toFixed(1)}` : ""}
            </div>
          ) : null}
        </div>
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2">
          <div className="mb-0.5 text-[10px] text-slate-500">Stop</div>
          <div className="font-mono text-[13px] font-medium text-rose-300">
            {fmt(entryTarget.stop_underlying)}
            {stopPremium ? <span className="ml-1 text-[11px]">{stopPremium}</span> : null}
          </div>
          {entryTarget.stop_brief ? (
            <div className="mt-0.5 line-clamp-1 text-[10px] text-slate-500">{entryTarget.stop_brief}</div>
          ) : null}
        </div>
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2">
          <div className="mb-0.5 text-[10px] text-slate-500">T1</div>
          <div className="font-mono text-[13px] font-medium text-emerald-300">
            {fmt(entryTarget.target_1)}
          </div>
          {entryTarget.rr_t1 != null ? (
            <div className="mt-0.5 text-[10px] text-slate-500">{entryTarget.rr_t1.toFixed(1)}x RR</div>
          ) : null}
        </div>
        <div className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2">
          <div className="mb-0.5 text-[10px] text-slate-500">T2</div>
          <div className="font-mono text-[13px] font-medium text-emerald-300">
            {fmt(entryTarget.target_2)}
          </div>
          {entryTarget.rr_t2 != null ? (
            <div className="mt-0.5 text-[10px] text-slate-500">{entryTarget.rr_t2.toFixed(1)}x RR</div>
          ) : null}
        </div>
      </div>

      {/* Target brief / RR brief */}
      {(entryTarget.target_brief || entryTarget.rr_brief) ? (
        <div className="mb-3 text-[11px] text-slate-500">
          {entryTarget.target_brief || entryTarget.rr_brief}
        </div>
      ) : null}

      {/* Magnet */}
      {entryTarget.price_magnet_strike ? (
        <div className={`mb-2 flex items-center gap-2 rounded-xl border px-3 py-2 text-[11px] ${
          magnetConflict
            ? "border-amber-400/25 bg-amber-400/8 text-amber-300"
            : "border-white/8 bg-[#0f1a27] text-amber-300"
        }`}>
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
          <span>
            Magnet {fmt(entryTarget.price_magnet_strike)}
            {magArrow ? ` ${magArrow}` : ""}
            {entryTarget.magnet_distance_pts != null ? ` ${Math.round(entryTarget.magnet_distance_pts)}pts` : ""}
            {entryTarget.magnet_character ? (
              <span className="ml-1 text-slate-400">· {String(entryTarget.magnet_character).replace(/[_-]+/g, " ")}</span>
            ) : null}
          </span>
          {magnetConflict ? (
            <span className="ml-auto shrink-0 text-[10px] text-amber-400">↑ against trade</span>
          ) : null}
        </div>
      ) : null}

      {/* Compression */}
      {entryTarget.compression_zone && entryTarget.price_magnet_strike && entryTarget.secondary_magnet ? (
        <div className="mb-2 rounded-xl border border-violet-400/20 bg-violet-400/8 px-3 py-2 text-[11px] text-violet-300">
          Compressed {fmt(entryTarget.price_magnet_strike)}–{fmt(entryTarget.secondary_magnet)}. Price pinned.
        </div>
      ) : null}

      {/* Walls */}
      <div className="flex gap-3 border-t border-white/8 pt-2 text-[10px] text-slate-500">
        <span>CE Wall <span className="text-slate-400">{fmt(entryTarget.call_wall_used)}</span></span>
        <span>PE Wall <span className="text-slate-400">{fmt(entryTarget.put_wall_used)}</span></span>
      </div>
    </section>
  );
}
