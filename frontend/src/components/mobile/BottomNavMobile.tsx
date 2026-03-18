import type { MobileNavKey } from "./types";

type BottomNavMobileProps = {
  active: MobileNavKey;
  onChange: (value: MobileNavKey) => void;
};

const NAV_ITEMS: Array<{ key: MobileNavKey; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "signal", label: "Signal" },
  { key: "heatmap", label: "Heatmap" },
  { key: "chart", label: "Charts" },
  { key: "settings", label: "Settings" },
];

function NavIcon({ itemKey, active }: { itemKey: MobileNavKey; active: boolean }) {
  const stroke = active ? "#38bdf8" : "#64748b";
  const fill = active ? "rgba(56,189,248,0.12)" : "rgba(148,163,184,0.08)";

  if (itemKey === "overview") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
        <rect x="3" y="4" width="5" height="16" rx="1.5" fill={fill} stroke={stroke} />
        <rect x="10" y="8" width="5" height="12" rx="1.5" fill={fill} stroke={stroke} />
        <rect x="17" y="2" width="4" height="18" rx="1.5" fill={fill} stroke={stroke} />
      </svg>
    );
  }

  if (itemKey === "signal") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
        <circle cx="11" cy="13" r="7" stroke={stroke} strokeWidth="1.8" />
        <circle cx="11" cy="13" r="3" fill={fill} stroke={stroke} strokeWidth="1.4" />
        <path d="M16.5 7.5L21 3" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" />
        <path d="M18 3h3v3" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (itemKey === "heatmap") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
        <path d="M12 2c2 3 1 4.8-.2 6.3C10 10.6 8 12.3 8 15a4 4 0 0 0 8 0c0-1.5-.6-2.7-1.7-4.1-.7-.9-.9-2 .1-3.9 1.8 1.2 3.6 3.9 3.6 7A6 6 0 0 1 6 14.7c0-4.1 2.3-7.9 6-12.7Z" fill={fill} stroke={stroke} strokeWidth="1.2" />
      </svg>
    );
  }

  if (itemKey === "chart") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2" fill={fill} stroke={stroke} />
        <path d="M6 16l4-4 3 2 5-6" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M6 8v8M10 6v10M14 10v6M18 7v9" stroke={stroke} strokeOpacity="0.55" strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="3" fill={fill} stroke={stroke} strokeWidth="1.6" />
      <path
        d="M12 3.5v2.2M12 18.3v2.2M20.5 12h-2.2M5.7 12H3.5M18 6l-1.6 1.6M7.6 16.4 6 18M18 18l-1.6-1.6M7.6 7.6 6 6"
        stroke={stroke}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function BottomNavMobile({ active, onChange }: BottomNavMobileProps) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-white/7 bg-[rgba(7,12,20,0.97)] px-2 py-2 backdrop-blur">
      <div className="grid grid-cols-5 gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive = item.key === active;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onChange(item.key)}
              className={`rounded-lg px-2 py-2 text-center transition ${
                isActive ? "bg-sky-400/10 text-sky-300" : "text-slate-500"
              }`}
            >
              <div className="flex justify-center">
                <NavIcon itemKey={item.key} active={isActive} />
              </div>
              <div className="mt-1 text-[9px] uppercase tracking-[0.05em]">{item.label}</div>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
