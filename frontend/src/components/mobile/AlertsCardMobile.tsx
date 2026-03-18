import type { MobileAlert } from "./types";

type AlertsCardMobileProps = {
  alerts: MobileAlert[];
};

export default function AlertsCardMobile({ alerts }: AlertsCardMobileProps) {
  if (!alerts.length) return null;

  return (
    <section className="mx-4 overflow-hidden rounded-[12px] border border-amber-300/20 bg-amber-300/5">
      <div className="flex items-center gap-2 border-b border-amber-300/10 px-4 py-3 text-[11px] uppercase tracking-[0.08em] text-amber-300">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-300 shadow-[0_0_8px_rgba(255,184,48,0.8)]" />
        Alerts
      </div>
      <div>
        {alerts.slice(0, 4).map((alert, index) => (
          <div key={`${alert.message}-${index}`} className="flex gap-2 border-b border-amber-300/8 px-4 py-3 text-sm text-slate-100 last:border-b-0">
            <span className="text-amber-300">.</span>
            <span>{alert.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
