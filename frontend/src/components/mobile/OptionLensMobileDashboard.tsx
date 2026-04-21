import { useState } from "react";
import MobileHeader from "./MobileHeader";
import SpotHeroCard from "./SpotHeroCard";
import PrimarySignalCard from "./PrimarySignalCard";
import StructuralRangeTrackMobile from "./StructuralRangeTrackMobile";
import TrapCardMobile from "./TrapCardMobile";
import KeyLevelsCard from "./KeyLevelsCard";
import TradePlanMobile from "./TradePlanMobile";
import AlertsCardMobile from "./AlertsCardMobile";
import BottomNavMobile from "./BottomNavMobile";
import type { MobileDashboardData, MobileNavKey, MobileOption } from "./types";

type OptionLensMobileDashboardProps = {
  data: MobileDashboardData;
  symbolOptions: MobileOption[];
  expiryOptions: MobileOption[];
  onSelectSymbol: (value: string) => void;
  onSelectExpiry: (value: string) => void;
};

export default function OptionLensMobileDashboard({
  data,
  symbolOptions: _symbolOptions,
  expiryOptions: _expiryOptions,
  onSelectSymbol: _onSelectSymbol,
  onSelectExpiry: _onSelectExpiry,
}: OptionLensMobileDashboardProps) {
  const [activeNav, setActiveNav] = useState<MobileNavKey>("overview");

  return (
    <div className="mx-auto flex h-dvh max-w-[480px] flex-col overflow-hidden bg-[#080f18] text-slate-100">
      <MobileHeader liveStatus={data.liveStatus} updatedAt={data.updatedAt} />

      <div className="flex-1 overflow-y-auto px-0 pb-[68px] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <SpotHeroCard
          symbol={data.symbol}
          expiry={data.expiry}
          spot={data.spot}
          spotChange={data.spotChange}
          openChange={data.openChange}
          pctChange={data.pctChange}
          updatedAt={data.updatedAt}
          regime={data.regime}
          projection={data.materialBreachConfirmed ? data.confirmationType || "Confirmed" : "No breakout"}
          dayTrend={data.dayTrend}
          longTrend={data.longTrend}
          sessionPhase={data.sessionPhase}
        />

        <StructuralRangeTrackMobile
          support={data.support}
          resistance={data.resistance}
          spot={data.spot}
          previousResistance={data.previousResistance}
          magnet={data.entryTarget?.price_magnet_strike ?? null}
          magnetPullDirection={data.entryTarget?.magnet_pull_direction ?? null}
          magnetDistancePts={data.entryTarget?.magnet_distance_pts ?? null}
          magnetCharacter={data.entryTarget?.magnet_character ?? null}
        />

        <PrimarySignalCard
          tradeAction={data.tradeAction}
          resolvedReason={data.resolvedReason}
          sessionPhase={data.sessionPhase}
          blockingReason={data.blockingReason}
          winningEngine={data.winningEngine}
          decisionConfidence={data.decisionConfidence}
          bias={data.bias}
          readinessScore={data.readinessScore}
          readinessState={data.readinessState}
          readinessExplainability={data.readinessExplainability ?? null}
          pressureState={data.pressureState}
          regime={data.regime}
          supportTransitionBadge={data.supportTransitionBadge}
          resistanceTransitionBadge={data.resistanceTransitionBadge}
        />

        <TrapCardMobile
          trapProbability={data.trapProbability}
          trapType={data.trapType}
          trapDirection={data.trapDirection}
          explanation={data.trapExplanation}
          severity={data.trapSeverity}
          affectedLevel={data.trapDirection === "downside" ? data.support : data.trapDirection === "upside" ? data.resistance : null}
        />

        <KeyLevelsCard
          support={data.support}
          resistance={data.resistance}
          bullishTrigger={data.bullishTrigger}
          bearishTrigger={data.bearishTrigger}
          breakoutUp={data.breakoutUp}
          breakoutDown={data.breakoutDown}
        />

        <TradePlanMobile
          tradeAction={data.tradeAction}
          bullishTrigger={data.bullishTrigger}
          bearishTrigger={data.bearishTrigger}
          support={data.support}
          resistance={data.resistance}
          entryTarget={data.entryTarget}
        />

        <AlertsCardMobile alerts={data.alerts} />
      </div>

      <BottomNavMobile active={activeNav} onChange={setActiveNav} />
    </div>
  );
}
