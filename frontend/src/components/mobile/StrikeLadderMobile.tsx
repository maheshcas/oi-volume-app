import type { MobileStrikeRow } from "./types";

type StrikeLadderMobileProps = {
  rows: MobileStrikeRow[];
};

function compactOi(value: number) {
  if (!Number.isFinite(value)) return "-";
  if (value >= 100000) return `${(value / 100000).toFixed(1)}L`;
  if (value >= 1000) return `${Math.round(value / 1000)}k`;
  return String(Math.round(value));
}

export default function StrikeLadderMobile({ rows }: StrikeLadderMobileProps) {
  if (!rows.length) {
    return (
      <section className="mx-4 overflow-hidden rounded-[12px] border border-white/7 bg-[#0d1520]">
        <div className="border-b border-white/7 px-4 py-3 text-[11px] uppercase tracking-[0.08em] text-slate-500">Strike Ladder</div>
        <div className="px-4 py-8 text-center text-sm text-slate-500">Ladder data is not available for this snapshot.</div>
      </section>
    );
  }

  const maxOi = rows.reduce((max, row) => Math.max(max, row.ceOI, row.peOI), 0);

  return (
    <section className="mx-4 overflow-hidden rounded-[12px] border border-white/7 bg-[#0d1520]">
      <div className="flex items-center justify-between border-b border-white/7 px-4 py-3">
        <div className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Strike Ladder</div>
        <div className="font-mono text-[10px] text-sky-300">{rows.length} strikes</div>
      </div>
      <div className="grid grid-cols-[1fr_80px_1fr] border-b border-white/7 px-4 py-2 text-[10px] uppercase tracking-[0.05em] text-slate-500">
        <div className="text-left text-rose-300">CE OI</div>
        <div className="text-center">Strike</div>
        <div className="text-right text-emerald-300">PE OI</div>
      </div>
      <div>
        {rows.map((row) => {
          const rowTone = row.isSpot
            ? "bg-sky-400/6"
            : row.isSupport
              ? "bg-emerald-400/5"
              : row.isResistance
                ? "bg-rose-400/5"
                : "";
          const ceWidth = maxOi > 0 ? `${Math.max(8, (row.ceOI / maxOi) * 100)}%` : "0%";
          const peWidth = maxOi > 0 ? `${Math.max(8, (row.peOI / maxOi) * 100)}%` : "0%";

          return (
            <div key={row.strike} className={`grid grid-cols-[1fr_80px_1fr] items-center border-b border-white/5 px-4 py-2 last:border-b-0 ${rowTone}`}>
              <div className="flex items-center gap-1.5">
                <div className="h-1 w-full max-w-[76px] rounded bg-white/5">
                  <div className="h-1 rounded bg-rose-400/70" style={{ width: ceWidth }} />
                </div>
                <span className={`font-mono text-[10px] ${row.isResistance ? "text-rose-300" : row.isSpot ? "text-sky-300" : "text-slate-500"}`}>
                  {compactOi(row.ceOI)}
                </span>
              </div>

              <div className="text-center">
                <div className={`font-mono text-[13px] font-medium ${row.isSpot ? "text-sky-300" : row.isResistance ? "text-rose-300" : row.isSupport ? "text-emerald-300" : "text-slate-100"}`}>
                  {row.strike.toLocaleString("en-IN")}
                </div>
                <div className={`mt-0.5 text-[9px] ${row.isResistance ? "text-rose-300/70" : row.isSupport ? "text-emerald-300/70" : row.isSpot ? "text-sky-300/70" : "text-slate-500"}`}>
                  {row.isSpot ? "ATM" : row.interpretation}
                </div>
              </div>

              <div className="flex items-center justify-end gap-1.5">
                <span className={`font-mono text-[10px] ${row.isSupport ? "text-emerald-300" : row.isSpot ? "text-sky-300" : "text-slate-500"}`}>
                  {compactOi(row.peOI)}
                </span>
                <div className="h-1 w-full max-w-[76px] rounded bg-white/5">
                  <div className="ml-auto h-1 rounded bg-emerald-400/70" style={{ width: peWidth }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
