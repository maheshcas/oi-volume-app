type MobileHeaderProps = {
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
};

const LIVE_LABELS: Record<MobileHeaderProps["liveStatus"], string> = {
  live: "LIVE",
  stale: "STALE",
  delayed: "DELAYED",
  blocked: "BLOCKED",
  checking: "CHECKING",
};

const LIVE_TONES: Record<MobileHeaderProps["liveStatus"], string> = {
  live: "text-emerald-300",
  stale: "text-amber-300",
  delayed: "text-rose-300",
  blocked: "text-rose-300",
  checking: "text-sky-300",
};

export default function MobileHeader({ liveStatus }: MobileHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/7 bg-[rgba(7,12,20,0.95)] px-4 py-3 backdrop-blur">
      <div className="flex items-center justify-between">
        <div className="font-['Syne'] text-base font-bold tracking-tight text-slate-50">
          Option<span className="text-sky-400">Lens</span>
        </div>
        <div className={`flex items-center gap-2 font-mono text-[11px] ${LIVE_TONES[liveStatus]}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current shadow-[0_0_10px_currentColor]" />
          {LIVE_LABELS[liveStatus]} · 15s
        </div>
      </div>
    </header>
  );
}
