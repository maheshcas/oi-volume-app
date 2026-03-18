import type { MobileNavKey } from "./types";

type BottomNavMobileProps = {
  active: MobileNavKey;
  onChange: (value: MobileNavKey) => void;
};

const NAV_ITEMS: Array<{ key: MobileNavKey; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "chart", label: "Chart" },
  { key: "ladder", label: "Ladder" },
  { key: "writers", label: "Writers" },
  { key: "alerts", label: "Alerts" },
];

function Icon({ name }: { name: MobileNavKey }) {
  if (name === "overview") {
    return <svg viewBox="0 0 18 18" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="9" cy="9" r="7" /><path d="M9 5v4l3 2" /></svg>;
  }
  if (name === "chart") {
    return <svg viewBox="0 0 18 18" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="2,14 6,8 10,11 14,5 16,5" /></svg>;
  }
  if (name === "ladder") {
    return <svg viewBox="0 0 18 18" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 5h14M2 9h10M2 13h12" /></svg>;
  }
  if (name === "writers") {
    return <svg viewBox="0 0 18 18" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="2" width="5" height="5" rx="1" /><rect x="11" y="2" width="5" height="5" rx="1" /><rect x="2" y="11" width="5" height="5" rx="1" /><rect x="11" y="11" width="5" height="5" rx="1" /></svg>;
  }
  return <svg viewBox="0 0 18 18" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 2a5 5 0 0 1 5 5c0 3 1 4 1.5 5H2.5C3 12 4 11 4 7a5 5 0 0 1 5-5z" /><circle cx="9" cy="15.5" r="0.5" fill="currentColor" /></svg>;
}

export default function BottomNavMobile({ active, onChange }: BottomNavMobileProps) {
  return (
    <nav className="mobile-bottom-nav sticky bottom-0 z-10 mt-auto flex h-[60px] shrink-0 border-t border-white/8 bg-[rgba(8,15,24,0.96)] backdrop-blur">
      {NAV_ITEMS.map((item) => {
        const isActive = item.key === active;
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onChange(item.key)}
            className={`mobile-bottom-nav-button flex flex-1 flex-col items-center justify-center gap-1 rounded-none bg-transparent text-[10px] font-medium transition-colors ${
              isActive ? "text-sky-300" : "text-slate-500"
            }`}
          >
            <div className={`flex h-[18px] items-center justify-center ${isActive ? "opacity-100" : "opacity-80"}`}>
              <Icon name={item.key} />
            </div>
            <span className="text-[9px] tracking-[0.04em]">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
