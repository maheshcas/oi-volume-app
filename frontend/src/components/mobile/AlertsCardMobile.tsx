import type { MobileAlert } from "./types";

type AlertsCardMobileProps = {
  alerts: MobileAlert[];
};

export default function AlertsCardMobile({ alerts }: AlertsCardMobileProps) {
  if (!alerts.length) return null;

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.07em] text-slate-600">Alerts</div>
      <div className="space-y-0.5">
        {alerts.slice(0, 4).map((alert, index) => {
          const tone = alert.severity === "watch" || alert.severity === "high" ? "bg-amber-300" : "bg-sky-400";
          return (
            <div key={`${alert.message}-${index}`} className="flex items-start gap-2 border-b border-white/8 py-2 text-[12px] leading-5 text-slate-400 last:border-b-0">
              <span className={`mt-1.5 h-1.5 w-1.5 rounded-full ${tone}`} />
              <span>{alert.message}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
