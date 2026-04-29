type MobileHeaderProps = {
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
  updatedAt: string;
  scheduleLabel?: string | null;
  onToggleTheme?: () => void;
  isDark?: boolean;
};

function statusTone(liveStatus: MobileHeaderProps["liveStatus"]) {
  if (liveStatus === "live") return "text-emerald-300 border-emerald-400/20 bg-emerald-400/10";
  if (liveStatus === "checking") return "text-sky-300 border-sky-400/20 bg-sky-400/10";
  return "text-amber-200 border-amber-300/20 bg-amber-300/10";
}

export default function MobileHeader({ liveStatus, updatedAt, scheduleLabel, onToggleTheme, isDark }: MobileHeaderProps) {
  return (
    <header className="shrink-0 border-b border-white/10 bg-[#0d1824] px-4 py-2">
      <div className="flex items-center justify-between text-[11px] font-medium text-slate-500">
        <span className="font-mono">{updatedAt || "--:--"}</span>
        <div className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 ${statusTone(liveStatus)}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {liveStatus === "live" ? "Live" : liveStatus.toUpperCase()}
        </div>
        <div className="flex items-center gap-2">
          {scheduleLabel ? (
            <span className="text-[10px] font-medium text-slate-500">{scheduleLabel}</span>
          ) : null}
          {onToggleTheme ? (
            <button
              type="button"
              onClick={onToggleTheme}
              className="flex h-6 w-6 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-slate-400"
              aria-label={isDark ? "Light mode" : "Dark mode"}
            >
              {isDark ? (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="5"/>
                  <line x1="12" y1="1" x2="12" y2="3"/>
                  <line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/>
                  <line x1="21" y1="12" x2="23" y2="12"/>
                </svg>
              ) : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
              )}
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
