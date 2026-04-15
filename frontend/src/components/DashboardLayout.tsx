import type { ReactNode } from "react";
import DecisionBanner from "./DecisionBanner";
import KeyLevelsCard from "./KeyLevelsCard";
import TrapCard from "./TrapCard";
import StructuralPriceContextCard from "./StructuralPriceContextCard";
import TradePlanCard from "./TradePlanCard";
import StrikeGuidanceCard from "./StrikeGuidanceCard";
import EntryTargetCard from "./EntryTargetCard";

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
    trapPct?: number | null;
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
    blockingReason?: string | null;
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
    spcState?: string | null;
    moveQuality?: string | null;
    spcDecision?: string | null;
    readinessScore?: number | null;
    readinessState?: string | null;
    readinessExplainability?: string | null;
    trapZoneLabel?: string;
    volumeLabel?: string;
    entryZone?: string | null;
    stopZone?: string | null;
    targetZone?: string | null;
    executionMode?: string | null;
    deltaGuidance?: string | null;
    bullishTrigger?: string | null;
    bearishTrigger?: string | null;
    invalidation?: string | null;
    peWall?: number | null;
    ceWall?: number | null;
    magnet?: number | null;
    maxPain?: number | null;
    strikeGap?: number | null;
    strikes?: Array<{
      strike: number;
      oi_ce: number;
      oi_pe: number;
      tag?: "pe_wall" | "ce_wall" | "magnet" | "maxpain" | null;
    }> | null;
  };
  tradePlan: {
    bias: string;
    regime?: string;
    plan: string;
    trapRisk: string;
    executionMode?: string;
    entryZone?: string;
    stopZone?: string;
    targetZone?: string;
    deltaGuidance?: string;
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
    oi_trap_signal?: string | null;
    oi_trap_confidence?: string | null;
    oi_trap_reason?: string | null;
    breach_level?: number | null;
    breach_oi_confirming?: boolean;
    oi_price_divergence?: boolean;
    absorption_detected?: boolean;
    absorption_message?: string | null;
    show_affected_level?: boolean;
    key_range?: string | null;
    institutional_levels?: string | null;
    market_insight?: string | null;
    putWall?: number;
    callWall?: number;
    oi_scenario?: string;
  };
  alerts: Array<{
    message: string;
    type: "primary" | "counter";
    severity: "info" | "watch" | "high";
  }>;
  strikeGuidance?: {
    recommended_action: string;
    option_type: string;
    suggested_strikes: any[];
    warnings: string[];
    theta_warning: boolean;
    days_to_expiry: number;
    iv_rank: number | null;
    iv_context: string | null;
    risk_reward_note: string | null;
    selling_favoured: boolean;
    position_size_fraction?: number | null;
    position_size_label?: string | null;
    execution_layer?: string | null;
    delta_guidance?: string | null;
    avoid_buying_premium?: boolean;
    entry_zone?: string | null;
    stop_zone?: string | null;
    target_zone?: string | null;
    strikeIntelligence?: {
      entry_signal?: string;
      entry_signal_reason?: string;
      entry_signal_strength?: string;
      recommended_action?: string;
      recommended_option?: string;
      recommended_strike?: number | null;
      trade_side?: string;
      position_size_fraction?: number;
      stop_description?: string;
      target_description?: string;
      delta_target_min?: number | null;
      delta_target_max?: number | null;
      max_pain_strike?: number | null;
      max_pain_pull?: string;
      iv_skew?: string;
      straddle_trend?: string;
      atm_straddle_premium?: number | null;
      ce_wall_holding?: boolean;
      pe_wall_holding?: boolean;
    } | null;
  } | null;
  entryTarget?: {
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
  } | null;
};

export default function DashboardLayout({
  decision,
  decisionLayer,
  keyLevels,
  structure,
  tradePlan,
  trap,
  alerts,
  strikeGuidance,
  entryTarget,
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
          trapPct={decision.trapPct}
          winningEngine={decision.winningEngine}
          decisionConfidence={decision.decisionConfidence}
          supportTransitionBadge={decision.supportTransitionBadge}
          resistanceTransitionBadge={decision.resistanceTransitionBadge}
        />
        {entryTarget ? (
          <div className="ia-decision-entry-target">
            <EntryTargetCard entryTarget={entryTarget} />
          </div>
        ) : null}
      </div>

      <div className="ia-layout-decision-layer">{false && decisionLayer}</div>

      <div className="ia-layout-levels">
        <div className="ia-card-stack">
          {false && <KeyLevelsCard
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
          />}
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
            blockingReason={structure.blockingReason}
            supportTransitionActive={structure.supportTransitionActive}
            supportTransitionBadge={structure.supportTransitionBadge}
            resistanceTransitionBadge={structure.resistanceTransitionBadge}
            breakoutProbabilityUp={structure.breakoutProbabilityUp}
            breakoutProbabilityDown={structure.breakoutProbabilityDown}
            trapProbability={structure.trapProbability}
            trapDirection={structure.trapDirection}
            spcState={structure.spcState}
            moveQuality={structure.moveQuality}
            spcDecision={structure.spcDecision}
            readinessScore={structure.readinessScore}
            readinessState={structure.readinessState}
            readinessExplainability={structure.readinessExplainability}
            bias={structure.bias}
            biasStrength={structure.biasStrength}
            regime={structure.regime}
            trapZoneLabel={structure.trapZoneLabel}
            volumeLabel={structure.volumeLabel}
            entryZone={structure.entryZone}
            stopZone={structure.stopZone}
            targetZone={structure.targetZone}
            executionMode={structure.executionMode}
            deltaGuidance={structure.deltaGuidance}
            bullishTrigger={structure.bullishTrigger}
            bearishTrigger={structure.bearishTrigger}
            invalidation={structure.invalidation}
            peWall={structure.peWall}
            ceWall={structure.ceWall}
            magnet={structure.magnet}
            maxPain={structure.maxPain}
            strikeGap={structure.strikeGap}
            strikes={structure.strikes}
          />
        </div>
      </div>

      <div className="ia-layout-playbook">
        {false && <TradePlanCard
          bias={tradePlan.bias}
          regime={tradePlan.regime}
          plan={tradePlan.plan}
          trapRisk={tradePlan.trapRisk}
          executionMode={tradePlan.executionMode}
          entryZone={tradePlan.entryZone}
          stopZone={tradePlan.stopZone}
          targetZone={tradePlan.targetZone}
          deltaGuidance={tradePlan.deltaGuidance}
          bullishTrigger={tradePlan.bullishTrigger}
          bearishTrigger={tradePlan.bearishTrigger}
          invalidation={tradePlan.invalidation}
        />}
      </div>
      {strikeGuidance ? (
        <div className="ia-layout-strike-guidance">
          <StrikeGuidanceCard
            recommended_action={strikeGuidance.recommended_action}
            option_type={strikeGuidance.option_type}
            suggested_strikes={strikeGuidance.suggested_strikes}
            warnings={strikeGuidance.warnings}
            theta_warning={strikeGuidance.theta_warning}
            days_to_expiry={strikeGuidance.days_to_expiry}
            iv_rank={strikeGuidance.iv_rank}
            iv_context={strikeGuidance.iv_context}
            risk_reward_note={strikeGuidance.risk_reward_note}
            selling_favoured={strikeGuidance.selling_favoured}
            position_size_fraction={strikeGuidance.position_size_fraction ?? null}
            position_size_label={strikeGuidance.position_size_label ?? null}
            execution_layer={strikeGuidance.execution_layer ?? null}
            delta_guidance={strikeGuidance.delta_guidance ?? null}
            avoid_buying_premium={Boolean(strikeGuidance.avoid_buying_premium)}
            entry_zone={strikeGuidance.entry_zone ?? null}
            stop_zone={strikeGuidance.stop_zone ?? null}
            target_zone={strikeGuidance.target_zone ?? null}
            strikeIntelligence={strikeGuidance.strikeIntelligence ?? null}
          />
        </div>
      ) : null}

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
            oi_trap_signal={trap.oi_trap_signal}
            oi_trap_confidence={trap.oi_trap_confidence}
            oi_trap_reason={trap.oi_trap_reason}
            breach_level={trap.breach_level}
            breach_oi_confirming={trap.breach_oi_confirming}
            oi_price_divergence={trap.oi_price_divergence}
            absorption_detected={trap.absorption_detected}
            absorption_message={trap.absorption_message}
            show_affected_level={trap.show_affected_level}
            key_range={trap.key_range}
            institutional_levels={trap.institutional_levels}
            market_insight={trap.market_insight}
            putWall={trap.putWall}
            callWall={trap.callWall}
            oi_scenario={trap.oi_scenario}
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
