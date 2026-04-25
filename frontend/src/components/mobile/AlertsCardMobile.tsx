import type { MobileAlert } from "./types";

type AlertsCardMobileProps = {
  alerts: MobileAlert[];
};

function alertDotClass(alert: MobileAlert): string {
  const sev = String(alert.severity || "").toLowerCase();
  if (sev === "high" || sev === "critical") return "bg-rose-400 shadow-[0_0_4px_rgba(248,113,113,0.6)]";
  if (sev === "watch" || sev === "warn" || sev === "warning") return "bg-amber-300";
  return "bg-slate-500 opacity-60";
}

function alertTextClass(alert: MobileAlert): string {
  const sev = String(alert.severity || "").toLowerCase();
  if (sev === "high" || sev === "critical") return "text-slate-200";
  return "text-slate-400";
}

export default function AlertsCardMobile({ alerts }: AlertsCardMobileProps) {
  if (!alerts.length) return null;

  const primary = alerts.filter(
    (a) => !String(a.severity || "").toLowerCase().includes("counter"),
  );
  const counter = alerts.filter((a) =>
    String(a.severity || "").toLowerCase().includes("counter"),
  );

  const sortedPrimary = [...primary].sort((a, b) => {
    const order: Record<string, number> = { high: 0, critical: 0, watch: 1, warn: 1, warning: 1 };
    const aRank = order[String(a.severity || "").toLowerCase()] ?? 2;
    const bRank = order[String(b.severity || "").toLowerCase()] ?? 2;
    return aRank - bRank;
  });

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-[0.07em] text-slate-600">
          Alerts
        </span>
        <span className="rounded-full bg-white/[0.04] px-2 py-0.5 font-mono text-[10px] text-slate-500">
          {alerts.length}
        </span>
      </div>
      <div className="space-y-0.5">
        {sortedPrimary.slice(0, 3).map((alert, index) => (
          <div
            key={`p-${index}`}
            className="flex items-start gap-2 border-b border-white/6 py-2 last:border-b-0"
          >
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${alertDotClass(alert)}`} />
            <span className={`text-[12px] leading-5 ${alertTextClass(alert)}`}>
              {alert.message}
            </span>
          </div>
        ))}
      </div>
      {counter.length > 0 ? (
        <div className="mt-2 border-t border-white/8 pt-2">
          <div className="mb-1.5 text-[9px] uppercase tracking-[0.08em] text-slate-600">
            Counter-trend
          </div>
          {counter.slice(0, 2).map((alert, index) => (
            <div
              key={`c-${index}`}
              className="flex items-start gap-2 border-b border-white/6 py-1.5 last:border-b-0"
            >
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-500 opacity-70" />
              <span className="text-[11px] italic leading-5 text-slate-500">
                {alert.message}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {alerts.length > 5 ? (
        <div className="mt-2 text-[10px] text-slate-600">
          +{alerts.length - 5} more alerts
        </div>
      ) : null}
    </section>
  );
}
