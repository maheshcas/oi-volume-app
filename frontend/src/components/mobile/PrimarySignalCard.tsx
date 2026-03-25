import {
  confidenceLabel,
  formatDecisionTime,
  friendlyBlockingReason,
  friendlyWinningEngine,
  type SignalHistoryItem,
} from "../decisionUx";

type PrimarySignalCardProps = {
  tradeAction: string;
  resolvedReason: string;
  bias: string;
  readinessScore: number | null;
  readinessState: string;
  pressureState: string;
  regime: string;
  blockingReason?: string;
  winningEngine?: string;
  decisionConfidence?: number | null;
  supportTransitionBadge?: boolean;
  resistanceTransitionBadge?: boolean;
  signalHistory?: SignalHistoryItem[];
};

function actionTone(action: string) {
  const text = action.toLowerCase();
  if (text.includes("long")) return "text-emerald-300";
  if (text.includes("short")) return "text-rose-300";
  return "text-amber-200";
}

function badgeTone(action: string) {
  const text = action.toLowerCase();
  if (text.includes("long")) return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";
  if (text.includes("short")) return "border-rose-400/20 bg-rose-400/10 text-rose-300";
  return "border-amber-300/20 bg-amber-300/10 text-amber-200";
}

function readinessTone(state: string) {
  const text = state.toLowerCase();
  if (text.includes("high")) return "text-emerald-300";
  if (text.includes("low")) return "text-rose-300";
  return "text-sky-300";
}

export default function PrimarySignalCard({
  tradeAction,
  resolvedReason,
  bias,
  readinessScore,
  readinessState,
  pressureState,
  regime,
  blockingReason = "NONE",
  winningEngine = "none",
  decisionConfidence = null,
  supportTransitionBadge = false,
  resistanceTransitionBadge = false,
  signalHistory = [],
}: PrimarySignalCardProps) {
  const readiness = typeof readinessScore === "number" ? Math.max(0, Math.min(100, readinessScore)) : 0;
  const confidence = typeof decisionConfidence === "number" ? Math.max(0, Math.min(100, decisionConfidence)) : 0;
  const confidenceState = confidenceLabel(decisionConfidence);
  const transitionLabel = supportTransitionBadge
    ? "Support Transition Active"
    : resistanceTransitionBadge
      ? "Resistance Transition Active"
      : null;
  const timelineItems = signalHistory.slice(-5).reverse();

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.07em] text-slate-600">Trade signal</div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className={`text-[26px] font-semibold tracking-[0.02em] ${actionTone(tradeAction)}`}>{tradeAction || "WAIT"}</div>
        <div className={`rounded-full border px-3 py-1 text-[11px] font-medium ${badgeTone(tradeAction)}`}>
          {typeof readinessScore === "number" ? `${Math.round(readinessScore)}% ${readinessState}` : readinessState || "-"}
        </div>
      </div>
      <div className="mb-3 text-[12px] leading-6 text-slate-400">
        {resolvedReason || "Trap risk elevated. Market still lacks confirmed directional expansion."}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {blockingReason !== "NONE" ? (
          <span className="rounded-full border border-rose-400/20 bg-rose-400/10 px-2.5 py-1 text-[10px] font-medium text-rose-200">
            Blocker: {friendlyBlockingReason(blockingReason)}
          </span>
        ) : null}
        <span className="rounded-full border border-sky-400/20 bg-sky-400/10 px-2.5 py-1 text-[10px] font-medium text-sky-200">
          {friendlyWinningEngine(winningEngine)}
        </span>
        {transitionLabel ? (
          <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2.5 py-1 text-[10px] font-medium text-amber-200">
            {transitionLabel}
          </span>
        ) : null}
      </div>

      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] text-slate-500">Trade readiness</span>
        <span className={`font-mono text-[13px] font-medium ${readinessTone(readinessState)}`}>
          {typeof readinessScore === "number" ? `${Math.round(readinessScore)}%` : "-"}
        </span>
      </div>
      <div className="relative mb-3 h-[5px] rounded-full bg-white/8">
        <div className="h-full rounded-full bg-[#5ba4e8] transition-all" style={{ width: `${readiness}%` }} />
        <div className="absolute left-[57%] top-[-5px] h-[15px] w-[1.5px] rounded bg-amber-300">
          <div className="absolute left-1/2 top-[-12px] -translate-x-1/2 whitespace-nowrap font-mono text-[9px] text-amber-300">
            57 entry
          </div>
        </div>
      </div>

      <div className="mb-3 rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2.5">
        <div className="mb-1 flex items-center justify-between gap-3">
          <span className="text-[10px] text-slate-600">Decision confidence</span>
          <span className="font-mono text-[12px] font-semibold text-slate-100">
            {Math.round(confidence)}% {confidenceState}
          </span>
        </div>
        <div className="h-[5px] rounded-full bg-white/8">
          <div className="h-full rounded-full bg-[#7be29d] transition-all" style={{ width: `${confidence}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {[
          ["Bias", bias],
          ["Pressure", pressureState],
          ["Regime", regime],
          ["Readiness state", readinessState],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2">
            <div className="mb-0.5 text-[10px] text-slate-600">{label}</div>
            <div className="text-[13px] font-medium text-slate-100">{value || "-"}</div>
          </div>
        ))}
      </div>

      {timelineItems.length ? (
        <div className="mt-3 rounded-xl border border-white/8 bg-[#0f1a27] px-3 py-2.5">
          <div className="mb-2 text-[10px] uppercase tracking-[0.07em] text-slate-600">Recent signal flow</div>
          <div className="space-y-1.5">
            {timelineItems.map((item, index) => (
              <div
                key={`${item.timestamp ?? "na"}-${item.trade_action ?? "na"}-${index}`}
                className="flex items-start gap-2 text-[11px] leading-5 text-slate-300"
              >
                <span className="min-w-[40px] font-mono text-slate-500">{formatDecisionTime(item.timestamp)}</span>
                <span className="min-w-[72px] font-medium text-slate-100">{item.trade_action || "-"}</span>
                <span className="text-slate-400">
                  {item.blocking_reason && item.blocking_reason !== "NONE"
                    ? friendlyBlockingReason(item.blocking_reason)
                    : item.resolved_reason || "-"}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
