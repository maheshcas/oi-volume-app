import StructuralPriceContextCard from "./StructuralPriceContextCard";

type CandlePoint = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

type StructuralChartCardProps = {
  candles: CandlePoint[];
  spotPrice: number | null;
  dayOpen?: number | null;
  dayHigh?: number | null;
  dayLow?: number | null;
  supportLevel?: number | null;
  resistanceLevel?: number | null;
  supportDefenseRatio?: number | null;
  resistanceDefenseRatio?: number | null;
  supportStart: number | null;
  supportEnd: number | null;
  resistanceStart: number | null;
  resistanceEnd: number | null;
  target1: number | null;
  target2: number | null;
  previousSupport?: number | null;
  previousResistance?: number | null;
  materialBreachConfirmed?: boolean;
  confirmationType?: string | null;
  bias: string;
  biasStrength: string;
  regime: string;
  trapZoneLabel?: string;
  volumeLabel?: string;
};

export default function StructuralChartCard(props: StructuralChartCardProps) {
  return (
    <div className="ia-card ia-structure-card">
      <StructuralPriceContextCard
        candles={props.candles}
        spotPrice={props.spotPrice}
        dayOpen={props.dayOpen}
        dayHigh={props.dayHigh}
        dayLow={props.dayLow}
        supportLevel={props.supportLevel}
        resistanceLevel={props.resistanceLevel}
        supportDefenseRatio={props.supportDefenseRatio}
        resistanceDefenseRatio={props.resistanceDefenseRatio}
        supportStart={props.supportStart}
        supportEnd={props.supportEnd}
        resistanceStart={props.resistanceStart}
        resistanceEnd={props.resistanceEnd}
        target1={props.target1}
        target2={props.target2}
        previousSupport={props.previousSupport}
        previousResistance={props.previousResistance}
        materialBreachConfirmed={props.materialBreachConfirmed}
        confirmationType={props.confirmationType}
        bias={props.bias}
        biasStrength={props.biasStrength}
        regime={props.regime}
        showPremiumOverlay={false}
        trapZoneLabel={props.trapZoneLabel}
        volumeLabel={props.volumeLabel}
      />
    </div>
  );
}
