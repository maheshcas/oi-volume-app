export type MobileNavKey = "overview" | "chart" | "ladder" | "writers" | "alerts";

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

export type MobileEntryTarget = {
  trade_type?: string;
  entry_underlying?: number | null;
  entry_option_strike?: number | null;
  entry_option_type?: string | null;
  entry_option_action?: string | null;
  entry_premium?: number | null;
  entry_brief?: string;
  stop_underlying?: number | null;
  stop_premium_value?: number | null;
  stop_brief?: string;
  target_1?: number | null;
  target_2?: number | null;
  target_brief?: string;
  rr_t1?: number | null;
  rr_t2?: number | null;
  rr_brief?: string;
  call_wall_used?: number | null;
  put_wall_used?: number | null;
  price_magnet_strike?: number | null;
  magnet_pull_direction?: string | null;
  magnet_distance_pts?: number | null;
  secondary_magnet?: number | null;
  magnet_character?: string | null;
  compression_zone?: boolean;
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
  blockingReason?: string;
  winningEngine?: string;
  decisionConfidence?: number | null;
  bias: string;
  dayTrend: string;
  longTrend: string;
  readinessScore: number | null;
  readinessState: string;
  readinessActive: boolean | null;
  readinessExplainability?: string | null;
  pressureState: string;
  regime: string;
  sessionPhase: string;
  absorptionDetected: boolean;
  absorptionLevel: number | null;
  absorptionMessage: string | null;
  supportTransitionActive: boolean;
  supportTransitionBadge?: boolean;
  resistanceTransitionBadge?: boolean;
  trapProbability: number | null;
  trapType: string;
  trapDirection?: "upside" | "downside" | "";
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
  previousResistance: number | null;
  putWall: number | null;
  callWall: number | null;
  entryTarget: MobileEntryTarget | null;
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
