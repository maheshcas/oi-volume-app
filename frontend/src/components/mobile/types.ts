export type MobileNavKey = "overview" | "signal" | "heatmap" | "chart" | "settings";

export type MobileOption = {
  label: string;
  value: string;
};

export type MobileStrikeRow = {
  strike: number;
  ceOI: number;
  peOI: number;
  interpretation: string;
  isSpot?: boolean;
  isSupport?: boolean;
  isResistance?: boolean;
};

export type MobileWriterRow = {
  strike: number;
  doi: number;
  volume: number;
};

export type MobileAlert = {
  message: string;
  severity?: string;
};

export type MobileDashboardData = {
  symbol: string;
  instrumentType: string;
  expiry: string | null;
  updatedAt: string;
  liveStatus: "live" | "stale" | "delayed" | "blocked" | "checking";
  spot: number | null;
  spotChange: string;
  openChange: string;
  pctChange: string;
  maxPain: string;
  pcr: string;
  tradeAction: string;
  resolvedReason: string;
  bias: string;
  readinessScore: number | null;
  readinessState: string;
  readinessActive: boolean | null;
  pressureState: string;
  regime: string;
  sessionPhase: string;
  absorptionDetected: boolean;
  absorptionLevel: number | null;
  absorptionMessage: string | null;
  supportTransitionActive: boolean;
  trapProbability: number | null;
  trapType: string;
  trapExplanation: string;
  trapSeverity: "low" | "moderate" | "high";
  support: number | null;
  resistance: number | null;
  bullishTrigger: string | null;
  bearishTrigger: string | null;
  breakoutUp: number | null;
  breakoutDown: number | null;
  materialBreachConfirmed: boolean;
  confirmationType: string | null;
  putWall: number | null;
  callWall: number | null;
  topWriters: {
    ce: MobileWriterRow[];
    pe: MobileWriterRow[];
  };
  futuresBasis: {
    syntheticFuture: number | null;
    basis: number | null;
    basisPct: number | null;
    basisType: string;
    direction: string;
  };
  alerts: MobileAlert[];
  ladderRows: MobileStrikeRow[];
};
