import type { ReactNode } from "react";
import DecisionBanner from "./DecisionBanner";
import HistoricalZoneContextCard from "./HistoricalZoneContextCard";
import KeyLevelsCard from "./KeyLevelsCard";
import TrapCard from "./TrapCard";
import StructuralPriceContextCard from "./StructuralPriceContextCard";
import TradePlanCard from "./TradePlanCard";

type DashboardLayoutProps = {
  decision: {
    action: "WAIT" | "CAUTION" | "READY";
    direction: "Bullish" | "Bearish" | "Neutral" | "Conflict";
    explanation: string;
    sessionPhase?: string | null;
    bias: string;
    readinessScore: number;
    readinessState: string;
    readinessExplainability?: string | null;
    pressureState: string;
    regime: string;
    detailSummary?: string;
    detailInsight?: string;
    detailWalls?: string | null;
    support: string;
    resistance: string;
    blockingReason?: string;
    winningEngine?: string;
    decisionConfidence?: number | null;
    supportTransitionBadge?: boolean;
    resistanceTransitionBadge?: boolean;
  };
  decisionLayer: ReactNode;
  keyLevels: {
    support: string;
    resistance: string;
    supportDefenseRatio?: number | null;
    resistanceDefenseRatio?: number | null;
    majorSupport?: string;
    majorResistance?: string;
    breakoutTrigger?: string;
    breakAbovePrimary: string;
    breakAboveExtended: string;
    breakBelowPrimary: string;
    breakBelowExtended: string;
    trapRisk: string;
    watchNote: string;
    breakoutProbability?: {
      upside?: number;
      downside?: number;
      upside_state?: string;
      downside_state?: string;
    };
  };
  historicalContext?: {
    available?: boolean;
    updatedAt?: string | null;
    fullWindow?: {
      zone_low?: number | null;
      zone_high?: number | null;
      center?: number | null;
      role?: string | null;
      score?: number | null;
      touches?: number | null;
      first_date?: string | null;
      last_date?: string | null;
    } | null;
    recentWindow?: {
      zone_low?: number | null;
      zone_high?: number | null;
      center?: number | null;
      role?: string | null;
      score?: number | null;
      touches?: number | null;
      first_date?: string | null;
      last_date?: string | null;
    } | null;
  };
  structure: {
    spotPrice: number | null;
    dayOpen?: number | null;
    dayHigh?: number | null;
    dayLow?: number | null;
    supportLevel?: number | null;
    resistanceLevel?: number | null;
    majorSupport?: number | null;
    majorResistance?: number | null;
    supportDefenseRatio?: number | null;
    resistanceDefenseRatio?: number | null;
    supportStart: number | null;
    supportEnd: number | null;
    resistanceStart: number | null;
    resistanceEnd: number | null;
    target1: number | null;
    target2: number | null;
    breakBelowPrimary?: string | null;
    breakAbovePrimary?: string | null;
    previousSupport?: number | null;
    previousResistance?: number | null;
    materialBreachConfirmed?: boolean;
    confirmationType?: string | null;
    sessionPhase?: string | null;
    tradeAction?: string | null;
    resolvedReason?: string | null;
    decisionExplanation?: string | null;
    decisionConfidence?: number | null;
    supportTransitionActive?: boolean;
    supportTransitionBadge?: boolean;
    resistanceTransitionBadge?: boolean;
    bias: string;
    biasStrength: string;
    regime: string;
    breakoutProbabilityUp?: number | null;
    breakoutProbabilityDown?: number | null;
    trapProbability?: number | null;
    trapDirection?: "upside" | "downside" | "";
    readinessScore?: number | null;
    readinessState?: string | null;
    readinessExplainability?: string | null;
    trapZoneLabel?: string;
    volumeLabel?: string;
  };
  tradePlan: {
    bias: string;
    regime?: string;
    plan: string;
    trapRisk: string;
    bullishTrigger?: string;
    bearishTrigger?: string;
    invalidation?: string;
  };
  trap: {
    trap_probability: number;
    trap_level: "Low" | "Moderate" | "High";
    trap_type: string;
    trap_zone: number;
    trap_direction?: "upside" | "downside" | "";
    suggested_action: string;
    trap_reason?: string | null;
    support_reason?: string | null;
    absorption_detected?: boolean;
    absorption_message?: string | null;
    show_affected_level?: boolean;
  };
  alerts: Array<{
    message: string;
    type: "primary" | "counter";
    severity: "info" | "watch" | "high";
  }>;
};

export default function DashboardLayout({
  decision,
  decisionLayer,
  keyLevels,
  historicalContext,
  structure,
  tradePlan,
  trap,
  alerts,
}: DashboardLayoutProps) {
  return (
    <div className="ia-dashboard-layout">
      <div className="ia-layout-decision">
        <DecisionBanner
          action={decision.action}
          direction={decision.direction}
          explanation={decision.explanation}
          sessionPhase={decision.sessionPhase}
          bias={decision.bias}
          readinessScore={decision.readinessScore}
          readinessState={decision.readinessState}
          readinessExplainability={decision.readinessExplainability}
          pressureState={decision.pressureState}
          regime={decision.regime}
          detailSummary={decision.detailSummary}
          detailInsight={decision.detailInsight}
          detailWalls={decision.detailWalls}
          support={decision.support}
          resistance={decision.resistance}
          blockingReason={decision.blockingReason}
          winningEngine={decision.winningEngine}
          decisionConfidence={decision.decisionConfidence}
          supportTransitionBadge={decision.supportTransitionBadge}
          resistanceTransitionBadge={decision.resistanceTransitionBadge}
        />
      </div>

      <div className="ia-layout-decision-layer">{decisionLayer}</div>

      <div className="ia-layout-levels">
        <div className="ia-card-stack">
          <KeyLevelsCard
            support={keyLevels.support}
            resistance={keyLevels.resistance}
            supportDefenseRatio={keyLevels.supportDefenseRatio}
            resistanceDefenseRatio={keyLevels.resistanceDefenseRatio}
            majorSupport={keyLevels.majorSupport}
            majorResistance={keyLevels.majorResistance}
            breakoutTrigger={keyLevels.breakoutTrigger}
            breakAbovePrimary={keyLevels.breakAbovePrimary}
            breakAboveExtended={keyLevels.breakAboveExtended}
            breakBelowPrimary={keyLevels.breakBelowPrimary}
            breakBelowExtended={keyLevels.breakBelowExtended}
            trapRisk={keyLevels.trapRisk}
            watchNote={keyLevels.watchNote}
            breakoutProbability={keyLevels.breakoutProbability}
          />
          <HistoricalZoneContextCard
            available={Boolean(historicalContext?.available)}
            updatedAt={historicalContext?.updatedAt ?? null}
            fullWindow={historicalContext?.fullWindow ?? null}
            recentWindow={historicalContext?.recentWindow ?? null}
          />
        </div>
      </div>


      <div className="ia-layout-structure">
        <div className="ia-card ia-structure-card">
          <StructuralPriceContextCard
            spotPrice={structure.spotPrice}
            dayOpen={structure.dayOpen}
            dayHigh={structure.dayHigh}
            dayLow={structure.dayLow}
            supportLevel={structure.supportLevel}
            resistanceLevel={structure.resistanceLevel}
            majorSupport={structure.majorSupport}
            majorResistance={structure.majorResistance}
            supportDefenseRatio={structure.supportDefenseRatio}
            resistanceDefenseRatio={structure.resistanceDefenseRatio}
            supportStart={structure.supportStart}
            supportEnd={structure.supportEnd}
            resistanceStart={structure.resistanceStart}
            resistanceEnd={structure.resistanceEnd}
            target1={structure.target1}
            target2={structure.target2}
            breakBelowPrimary={structure.breakBelowPrimary}
            breakAbovePrimary={structure.breakAbovePrimary}
            previousSupport={structure.previousSupport}
            previousResistance={structure.previousResistance}
            materialBreachConfirmed={structure.materialBreachConfirmed}
            confirmationType={structure.confirmationType}
            sessionPhase={structure.sessionPhase}
            tradeAction={structure.tradeAction}
            resolvedReason={structure.resolvedReason}
            decisionExplanation={structure.decisionExplanation}
            decisionConfidence={structure.decisionConfidence}
            supportTransitionActive={structure.supportTransitionActive}
            supportTransitionBadge={structure.supportTransitionBadge}
            resistanceTransitionBadge={structure.resistanceTransitionBadge}
            breakoutProbabilityUp={structure.breakoutProbabilityUp}
            breakoutProbabilityDown={structure.breakoutProbabilityDown}
            trapProbability={structure.trapProbability}
            trapDirection={structure.trapDirection}
            readinessScore={structure.readinessScore}
            readinessState={structure.readinessState}
            readinessExplainability={structure.readinessExplainability}
            bias={structure.bias}
            biasStrength={structure.biasStrength}
            regime={structure.regime}
            trapZoneLabel={structure.trapZoneLabel}
            volumeLabel={structure.volumeLabel}
          />
        </div>
      </div>

      <div className="ia-layout-playbook">
        <TradePlanCard
          bias={tradePlan.bias}
          regime={tradePlan.regime}
          plan={tradePlan.plan}
          trapRisk={tradePlan.trapRisk}
          bullishTrigger={tradePlan.bullishTrigger}
          bearishTrigger={tradePlan.bearishTrigger}
          invalidation={tradePlan.invalidation}
        />
      </div>

      <div className="ia-layout-trap">
        <div className="ia-card">
          <h3 className="ia-card-title">Trap</h3>
          <TrapCard
            trap_probability={trap.trap_probability}
            trap_level={trap.trap_level}
            trap_type={trap.trap_type}
            trap_zone={trap.trap_zone}
            trap_direction={trap.trap_direction}
            suggested_action={trap.suggested_action}
            trap_reason={trap.trap_reason}
            support_reason={trap.support_reason}
            absorption_detected={trap.absorption_detected}
            absorption_message={trap.absorption_message}
            show_affected_level={trap.show_affected_level}
          />
          {alerts.length ? (
            <div className="ia-trap-alerts">
              <div className="ia-kpi-label">Alerts</div>
              <div className="ia-trap-alert-list">
                {alerts.slice(0, 4).map((item, idx) => (
                  <span
                    key={idx}
                    className={`alert-item alert-item-${item.severity} ${item.type === "counter" ? "alert-item-counter" : ""}`}
                  >
                    {item.message}
                    {item.type === "counter" ? " (Counter-trend)" : ""}
                  </span>
                ))}
                {alerts.length > 4 ? (
                  <span className="alert-item alert-item-info ia-alert-more">
                    +{alerts.length - 4} more alerts
                  </span>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>

    </div>
  );
}
