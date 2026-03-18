import { useState } from "react";
import MobileHeader from "./MobileHeader";
import SpotHeroCard from "./SpotHeroCard";
import PrimarySignalCard from "./PrimarySignalCard";
import AbsorptionAlertCard from "./AbsorptionAlertCard";
import TrapCardMobile from "./TrapCardMobile";
import KeyLevelsCard from "./KeyLevelsCard";
import SessionPhaseCard from "./SessionPhaseCard";
import StrikeLadderMobile from "./StrikeLadderMobile";
import BottomNavMobile from "./BottomNavMobile";
import TopWritersMobile from "./TopWritersMobile";
import FuturesBasisCardMobile from "./FuturesBasisCardMobile";
import AlertsCardMobile from "./AlertsCardMobile";
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
  symbolOptions,
  expiryOptions,
  onSelectSymbol,
  onSelectExpiry,
}: OptionLensMobileDashboardProps) {
  const [activeNav, setActiveNav] = useState<MobileNavKey>("overview");

  return (
    <div className="min-h-screen bg-[#070c14] pb-24 text-slate-100">
      <MobileHeader liveStatus={data.liveStatus} />

      <div className="space-y-3 pb-4">
        <section className="border-b border-white/7">
          <div className="flex gap-2 overflow-x-auto px-4 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {symbolOptions.map((option) => {
              const active = option.value === data.symbol;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onSelectSymbol(option.value)}
                  className={`shrink-0 rounded-full border px-4 py-1.5 font-mono text-xs ${
                    active ? "border-sky-400 bg-sky-400 text-slate-950" : "border-white/10 text-slate-500"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          <div className="flex gap-2 overflow-x-auto border-t border-white/7 px-4 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {expiryOptions.map((option) => {
              const active = option.value === (data.expiry ?? "");
              return (
                <button
                  key={option.value || "auto"}
                  type="button"
                  onClick={() => onSelectExpiry(option.value)}
                  className={`shrink-0 rounded-full border px-3 py-1.5 font-mono text-[11px] ${
                    active
                      ? "border-cyan-300/30 bg-cyan-300/10 text-cyan-200"
                      : "border-white/10 text-slate-500"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </section>

        <SpotHeroCard
          symbol={data.symbol}
          spot={data.spot}
          spotChange={data.spotChange}
          openChange={data.openChange}
          pctChange={data.pctChange}
          maxPain={data.maxPain}
          pcr={data.pcr}
          updatedAt={data.updatedAt}
        />

        <SessionPhaseCard
          sessionPhase={data.sessionPhase}
          regime={data.regime}
          pressureState={data.pressureState}
          readinessActive={data.readinessActive}
        />

        <PrimarySignalCard
          tradeAction={data.tradeAction}
          resolvedReason={data.resolvedReason}
          bias={data.bias}
          readinessScore={data.readinessScore}
          readinessState={data.readinessState}
          pressureState={data.pressureState}
          regime={data.regime}
        />

        {data.absorptionDetected || data.absorptionMessage ? (
          <AbsorptionAlertCard
            absorptionLevel={data.absorptionLevel}
            absorptionMessage={data.absorptionMessage}
            supportTransitionActive={data.supportTransitionActive}
          />
        ) : null}

        <TrapCardMobile
          trapProbability={data.trapProbability}
          trapType={data.trapType}
          explanation={data.trapExplanation}
          severity={data.trapSeverity}
        />

        <KeyLevelsCard
          support={data.support}
          resistance={data.resistance}
          bullishTrigger={data.bullishTrigger}
          bearishTrigger={data.bearishTrigger}
          breakoutUp={data.breakoutUp}
          breakoutDown={data.breakoutDown}
        />

        <StrikeLadderMobile rows={data.ladderRows} />

        <TopWritersMobile ce={data.topWriters.ce} pe={data.topWriters.pe} />

        <FuturesBasisCardMobile
          syntheticFuture={data.futuresBasis.syntheticFuture}
          basis={data.futuresBasis.basis}
          basisPct={data.futuresBasis.basisPct}
          basisType={data.futuresBasis.basisType}
          direction={data.futuresBasis.direction}
        />

        <AlertsCardMobile alerts={data.alerts} />

        <div className="px-4 text-center text-[10px] leading-6 text-slate-500">
          Educational and analytical purposes only. Not SEBI registered. No buy/sell recommendation.
        </div>

        <BottomNavMobile active={activeNav} onChange={setActiveNav} />
      </div>
    </div>
  );
}
