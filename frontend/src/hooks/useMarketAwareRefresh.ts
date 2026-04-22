import { useEffect, useState } from "react";

const MARKET_OPEN_MIN = 9 * 60;
const MARKET_CLOSE_MIN = 15 * 60 + 45;

export const NSE_HOLIDAYS_2026: ReadonlySet<string> = new Set([
  "2026-01-26",
  "2026-02-17",
  "2026-03-03",
  "2026-03-20",
  "2026-04-03",
  "2026-04-14",
  "2026-05-01",
  "2026-05-27",
  "2026-06-26",
  "2026-08-15",
  "2026-08-26",
  "2026-10-02",
  "2026-10-20",
  "2026-11-09",
  "2026-11-10",
  "2026-11-24",
  "2026-12-25",
]);

export const NSE_HOLIDAYS: ReadonlySet<string> = NSE_HOLIDAYS_2026;

export function toISTParts(now: Date = new Date()): {
  year: number;
  month: number;
  day: number;
  dow: number;
  hour: number;
  minute: number;
  dateKey: string;
  minutesSinceMidnight: number;
} {
  // `getTime()` is already UTC epoch milliseconds.
  // Add IST offset directly to avoid double-applying local timezone offsets.
  const istMs = now.getTime() + (5 * 60 + 30) * 60_000;
  const ist = new Date(istMs);
  const year = ist.getUTCFullYear();
  const month = ist.getUTCMonth() + 1;
  const day = ist.getUTCDate();
  const hour = ist.getUTCHours();
  const minute = ist.getUTCMinutes();
  const pad = (n: number) => n.toString().padStart(2, "0");
  return {
    year,
    month,
    day,
    dow: ist.getUTCDay(),
    hour,
    minute,
    dateKey: `${year}-${pad(month)}-${pad(day)}`,
    minutesSinceMidnight: hour * 60 + minute,
  };
}

export type MarketSessionState =
  | "open"
  | "closed-weekend"
  | "closed-holiday"
  | "closed-after-hours"
  | "closed-pre-market";

export function resolveMarketSession(
  now: Date = new Date(),
  holidays: ReadonlySet<string> = NSE_HOLIDAYS,
): { state: MarketSessionState; isOpen: boolean; istParts: ReturnType<typeof toISTParts> } {
  const parts = toISTParts(now);
  if (parts.dow === 0 || parts.dow === 6) {
    return { state: "closed-weekend", isOpen: false, istParts: parts };
  }
  if (holidays.has(parts.dateKey)) {
    return { state: "closed-holiday", isOpen: false, istParts: parts };
  }
  if (parts.minutesSinceMidnight < MARKET_OPEN_MIN) {
    return { state: "closed-pre-market", isOpen: false, istParts: parts };
  }
  if (parts.minutesSinceMidnight >= MARKET_CLOSE_MIN) {
    return { state: "closed-after-hours", isOpen: false, istParts: parts };
  }
  return { state: "open", isOpen: true, istParts: parts };
}

export const MARKET_OPEN_REFRESH_MS = 15_000;
export const MARKET_CLOSED_REFRESH_MS = 60_000;
export const MARKET_OPEN_SPOT_REFRESH_MS = 2_000;
export const MARKET_CLOSED_SPOT_REFRESH_MS = 60_000;

export function useMarketAwareRefresh(): {
  session: MarketSessionState;
  isOpen: boolean;
  refreshMs: number;
  spotRefreshMs: number;
  label: string;
  istClock: string;
} {
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = setInterval(() => {
      setNow(new Date());
    }, 1_000);
    return () => clearInterval(id);
  }, []);

  const { state, isOpen, istParts } = resolveMarketSession(now);

  const refreshMs = isOpen ? MARKET_OPEN_REFRESH_MS : MARKET_CLOSED_REFRESH_MS;
  const spotRefreshMs = isOpen ? MARKET_OPEN_SPOT_REFRESH_MS : MARKET_CLOSED_SPOT_REFRESH_MS;

  const pad = (n: number) => n.toString().padStart(2, "0");
  const istClock = `${pad(istParts.hour)}:${pad(istParts.minute)} IST`;

  const label =
    state === "open"
      ? "Live · every 15s"
      : state === "closed-weekend"
        ? "Weekend · every 1m"
        : state === "closed-holiday"
          ? "Holiday · every 1m"
          : state === "closed-pre-market"
            ? "Pre-market · every 1m"
            : "After hours · every 1m";

  return { session: state, isOpen, refreshMs, spotRefreshMs, label, istClock };
}
