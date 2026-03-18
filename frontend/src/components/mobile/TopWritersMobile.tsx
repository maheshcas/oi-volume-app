import { useState } from "react";
import type { MobileWriterRow } from "./types";

type TopWritersMobileProps = {
  ce: MobileWriterRow[];
  pe: MobileWriterRow[];
};

function compactIndian(value: number) {
  if (!Number.isFinite(value)) return "-";
  return Math.round(value).toLocaleString("en-IN");
}

export default function TopWritersMobile({ ce, pe }: TopWritersMobileProps) {
  const [active, setActive] = useState<"ce" | "pe">("ce");
  const rows = active === "ce" ? ce : pe;

  return (
    <section className="mx-4 overflow-hidden rounded-[12px] border border-white/7 bg-[#0d1520]">
      <div className="border-b border-white/7 px-4 py-3 text-[11px] uppercase tracking-[0.08em] text-slate-500">
        Top Writers Activity
      </div>
      <div className="flex border-b border-white/7">
        <button
          type="button"
          onClick={() => setActive("ce")}
          className={`flex-1 border-b-2 px-3 py-2 text-[11px] font-medium ${
            active === "ce" ? "border-rose-400 text-rose-300" : "border-transparent text-slate-500"
          }`}
        >
          Call Writers (CE)
        </button>
        <button
          type="button"
          onClick={() => setActive("pe")}
          className={`flex-1 border-b-2 px-3 py-2 text-[11px] font-medium ${
            active === "pe" ? "border-emerald-400 text-emerald-300" : "border-transparent text-slate-500"
          }`}
        >
          Put Writers (PE)
        </button>
      </div>
      <div className="px-4 py-2">
        {rows.length ? (
          rows.map((row) => (
            <div key={`${active}-${row.strike}`} className="flex items-center justify-between border-b border-white/7 py-3 last:border-b-0">
              <div className="font-mono text-sm font-medium text-slate-100">
                {row.strike.toLocaleString("en-IN")}
              </div>
              <div className="text-right">
                <div className={`font-mono text-xs ${active === "ce" ? "text-rose-300" : "text-emerald-300"}`}>
                  OI+ {compactIndian(row.doi)}
                </div>
                <div className="mt-1 text-[10px] text-slate-500">Vol {compactIndian(row.volume)}</div>
              </div>
            </div>
          ))
        ) : (
          <div className="py-6 text-center text-sm text-slate-500">No writers activity available.</div>
        )}
      </div>
    </section>
  );
}
