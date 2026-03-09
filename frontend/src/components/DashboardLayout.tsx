import type { ReactNode } from "react";
import DecisionBanner from "./DecisionBanner";
import KeyLevelsCard from "./KeyLevelsCard";
import TrapCard from "./TrapCard";
import StructuralChartCard from "./StructuralChartCard";
import TradePlanCard from "./TradePlanCard";
import AdvancedAnalysisCard from "./AdvancedAnalysisCard";

type CandlePoint = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

type DashboardLayoutProps = {
  decision: {
    action: "WAIT" | "CAUTION" | "READY";
    direction: "Bullish" | "Bearish" | "Neutral" | "Conflict";
    explanation: string;
    support: string;
    resistance: string;
  };
  decisionLayer: ReactNode;
  keyLevels: {
    support: string;
    resistance: string;
    breakAbovePrimary: string;
    breakAboveExtended: string;
    breakBelowPrimary: string;
    breakBelowExtended: string;
    trapRisk: string;
    watchNote: string;
  };
  structure: {
    candles: CandlePoint[];
    spotPrice: number | null;
    dayOpen?: number | null;
    dayHigh?: number | null;
    dayLow?: number | null;
    supportLevel?: number | null;
    resistanceLevel?: number | null;
    supportStart: number | null;
    supportEnd: number | null;
    resistanceStart: number | null;
    resistanceEnd: number | null;
    target1: number | null;
    target2: number | null;
    bias: string;
    biasStrength: string;
    regime: string;
    trapZoneLabel?: string;
    volumeLabel?: string;
  };
  tradePlan: {
    bias: string;
    regime?: string;
    plan: string;
    trapRisk: string;
  };
  trap: {
    trap_probability: number;
    trap_level: "Low" | "Moderate" | "High";
    trap_type: string;
    trap_zone: number;
    suggested_action: string;
    show_affected_level?: boolean;
  };
  advanced: {
    open: boolean;
    onToggle: () => void;
    preview: string;
    content: ReactNode;
  };
};

export default function DashboardLayout({
  decision,
  decisionLayer,
  keyLevels,
  structure,
  tradePlan,
  trap,
  advanced,
}: DashboardLayoutProps) {
  return (
    <div
      className="ia-dashboard-layout"
      style={{
        gridTemplateAreas: `
          "decision levels trap"
          "decisionlayer levels trap"
          "structure structure playbook"
          "structure structure advanced"
        `,
      }}
    >
      <div className="ia-layout-decision">
        <DecisionBanner
          action={decision.action}
          direction={decision.direction}
          explanation={decision.explanation}
          support={decision.support}
          resistance={decision.resistance}
        />
      </div>

      <div className="ia-layout-decision-layer">{decisionLayer}</div>

      <div className="ia-layout-levels">
        <KeyLevelsCard
          support={keyLevels.support}
          resistance={keyLevels.resistance}
          breakAbovePrimary={keyLevels.breakAbovePrimary}
          breakAboveExtended={keyLevels.breakAboveExtended}
          breakBelowPrimary={keyLevels.breakBelowPrimary}
          breakBelowExtended={keyLevels.breakBelowExtended}
          trapRisk={keyLevels.trapRisk}
          watchNote={keyLevels.watchNote}
        />
      </div>

      <div className="ia-layout-structure">
        <StructuralChartCard
          candles={structure.candles}
          spotPrice={structure.spotPrice}
          dayOpen={structure.dayOpen}
          dayHigh={structure.dayHigh}
          dayLow={structure.dayLow}
          supportLevel={structure.supportLevel}
          resistanceLevel={structure.resistanceLevel}
          supportStart={structure.supportStart}
          supportEnd={structure.supportEnd}
          resistanceStart={structure.resistanceStart}
          resistanceEnd={structure.resistanceEnd}
          target1={structure.target1}
          target2={structure.target2}
          bias={structure.bias}
          biasStrength={structure.biasStrength}
          regime={structure.regime}
          trapZoneLabel={structure.trapZoneLabel}
          volumeLabel={structure.volumeLabel}
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
            suggested_action={trap.suggested_action}
            show_affected_level={trap.show_affected_level}
          />
        </div>
      </div>

      <div className="ia-layout-playbook">
        <TradePlanCard
          bias={tradePlan.bias}
          regime={tradePlan.regime}
          plan={tradePlan.plan}
          trapRisk={tradePlan.trapRisk}
        />
      </div>

      <div className="ia-layout-advanced">
        <AdvancedAnalysisCard
          open={advanced.open}
          onToggle={advanced.onToggle}
          preview={advanced.preview}
        >
          {advanced.content}
        </AdvancedAnalysisCard>
      </div>
    </div>
  );
}
