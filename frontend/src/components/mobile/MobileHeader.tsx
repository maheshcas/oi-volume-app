type MobileHeaderProps = {
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
  updatedAt: string;
  scheduleLabel?: string | null;
};

function statusTone(liveStatus: MobileHeaderProps["liveStatus"]) {
  if (liveStatus === "live") return "text-emerald-300 border-emerald-400/20 bg-emerald-400/10";
  if (liveStatus === "checking") return "text-sky-300 border-sky-400/20 bg-sky-400/10";
  return "text-amber-200 border-amber-300/20 bg-amber-300/10";
}

export default function MobileHeader({ liveStatus, updatedAt, scheduleLabel }: MobileHeaderProps) {
  return (
    <header className="shrink-0 border-b border-white/10 bg-[#0d1824] px-4 py-2">
      <div className="flex items-center justify-between text-[11px] font-medium text-slate-500">
        <span className="font-mono">{updatedAt || "--:--"}</span>
        <div className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 ${statusTone(liveStatus)}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {liveStatus === "live" ? "Live" : liveStatus.toUpperCase()}
        </div>
        {scheduleLabel ? (
          <span className="text-[10px] font-medium text-slate-500">
            {scheduleLabel}
          </span>
        ) : (
          <span className="font-mono tracking-[0.14em] text-slate-600">●●●</span>
        )}
      </div>
    </header>
  );
}
