type FuturesBasisCardMobileProps = {
  syntheticFuture: number | null;
  basis: number | null;
  basisPct: number | null;
  basisType: string;
  direction: string;
};

function formatNumber(value: number | null, digits = 2) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export default function FuturesBasisCardMobile(props: FuturesBasisCardMobileProps) {
  const basisTone =
    props.basisType.toLowerCase() === "premium"
      ? "text-emerald-300"
      : props.basisType.toLowerCase() === "discount"
        ? "text-rose-300"
        : "text-slate-200";

  return (
    <section>
      <div className="px-4 pb-2 text-[11px] uppercase tracking-[0.08em] text-slate-500">Futures Basis</div>
      <div className="mx-4 rounded-[12px] border border-white/7 bg-[#0d1520] px-4 py-2">
        <div className="flex items-center justify-between border-b border-white/7 py-3 text-sm last:border-b-0">
          <span className="text-slate-500">Synthetic Future</span>
          <span className="font-mono text-slate-100">{formatNumber(props.syntheticFuture)}</span>
        </div>
        <div className="flex items-center justify-between border-b border-white/7 py-3 text-sm last:border-b-0">
          <span className="text-slate-500">Basis</span>
          <span className={`font-mono ${basisTone}`}>
            {typeof props.basis === "number"
              ? `${formatNumber(props.basis)} (${formatNumber(props.basisPct)}%)`
              : "-"}
          </span>
        </div>
        <div className="flex items-center justify-between border-b border-white/7 py-3 text-sm last:border-b-0">
          <span className="text-slate-500">Status</span>
          <span className={`font-mono ${basisTone}`}>{props.basisType || "-"}</span>
        </div>
        <div className="flex items-center justify-between py-3 text-sm">
          <span className="text-slate-500">Directional</span>
          <span className="font-mono text-slate-100">{props.direction || "-"}</span>
        </div>
      </div>
    </section>
  );
}
