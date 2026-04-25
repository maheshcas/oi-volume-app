import {
  confidenceLabel,
  friendlyBlockingReason,
  friendlyWinningEngine,
} from "../decisionUx";

// ── Unlock gate helpers (mirrors desktop Patch B logic) ──────────────────

type MobileGateStatus = "pass" | "near" | "fail" | "unknown";

type MobileGate = {
  key: string;
  label: string;
  status: MobileGateStatus;
  current: string;
  gap: string | null;
};

function resolveGatesMobile(args: {
  trapPct: number | null | undefined;
  spot: number | null | undefined;
  support: number | null | undefined;
  resistance: number | null | undefined;
  readinessScore: number | null;
  decisionConfidence: number | null | undefined;
}): MobileGate[] {
  const gates: MobileGate[] = [];

  const trap =
    typeof args.trapPct === "number" && Number.isFinite(args.trapPct)
      ? Math.round(args.trapPct)
      : null;
  if (trap !== null) {
    const status: MobileGateStatus =
      trap < 55 ? "pass" : trap < 60 ? "near" : "fail";
    gates.push({
      key: "trap",
      label: "Trap < 55%",
      status,
      current: `${trap}%`,
      gap: status === "pass" ? null : `drop ${trap - 54}%`,
    });
  }

  const spot =
    typeof args.spot === "number" && Number.isFinite(args.spot) ? args.spot : null;
  const support =
    typeof args.support === "number" && Number.isFinite(args.support)
      ? args.support
      : null;
  const resistance =
    typeof args.resistance === "number" && Number.isFinite(args.resistance)
      ? args.resistance
      : null;
  if (spot !== null && (support !== null || resistance !== null)) {
    const distToS = support !== null ? Math.abs(spot - support) : Infinity;
    const distToR = resistance !== null ? Math.abs(spot - resistance) : Infinity;
    const nearest = Math.min(distToS, distToR);
    const side = distToS < distToR ? "S" : "R";
    const status: MobileGateStatus =
      nearest <= 60 ? "pass" : nearest <= 100 ? "near" : "fail";
    gates.push({
      key: "edge",
      label: "Spot at S/R edge",
      status,
      current: `${Math.round(nearest)}pts to ${side}`,
      gap: status === "pass" ? null : `need ${Math.round(nearest - 60)}pts`,
    });
  }

  const readiness = Math.max(0, Math.min(100, Number(args.readinessScore) || 0));
  const rStatus: MobileGateStatus =
    readiness >= 60 ? "pass" : readiness >= 50 ? "near" : "fail";
  gates.push({
    key: "readiness",
    label: "Readiness ≥ 60%",
    status: rStatus,
    current: `${Math.round(readiness)}%`,
    gap: rStatus === "pass" ? null : `gain ${Math.round(60 - readiness)}%`,
  });

  const conf =
    typeof args.decisionConfidence === "number" &&
    Number.isFinite(args.decisionConfidence)
      ? Math.max(0, Math.min(100, args.decisionConfidence))
      : null;
  if (conf !== null) {
    const cStatus: MobileGateStatus =
      conf >= 50 ? "pass" : conf >= 40 ? "near" : "fail";
    gates.push({
      key: "confidence",
      label: "Confidence ≥ 50%",
      status: cStatus,
      current: `${Math.round(conf)}%`,
      gap: cStatus === "pass" ? null : `gain ${Math.round(50 - conf)}%`,
    });
  }

  return gates;
}

type PrimarySignalCardProps = {
  tradeAction: string;
  resolvedReason: string;
  sessionPhase?: string;
  bias: string;
  readinessScore: number | null;
  readinessState: string;
  readinessExplainability?: string | null;
  pressureState: string;
  regime: string;
  blockingReason?: string;
  winningEngine?: string;
  decisionConfidence?: number | null;
  supportTransitionBadge?: boolean;
  resistanceTransitionBadge?: boolean;
  trapProbability?: number | null;
  spot?: number | null;
  support?: number | null;
  resistance?: number | null;
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
  if (text.includes("ready") && !text.includes("not")) return "text-emerald-300";
  if (text.includes("not")) return "text-rose-300";
  return "text-sky-300";
}

export default function PrimarySignalCard({
  tradeAction,
  resolvedReason,
  sessionPhase,
  bias,
  readinessScore,
  readinessState,
  readinessExplainability = null,
  pressureState,
  regime,
  blockingReason = "NONE",
  winningEngine = "none",
  decisionConfidence = null,
  supportTransitionBadge = false,
  resistanceTransitionBadge = false,
  trapProbability = null,
  spot = null,
  support = null,
  resistance = null,
}: PrimarySignalCardProps) {
  const readiness = typeof readinessScore === "number" ? Math.max(0, Math.min(100, readinessScore)) : 0;
  const confidence = typeof decisionConfidence === "number" ? Math.max(0, Math.min(100, decisionConfidence)) : 0;
  const confidenceState = confidenceLabel(decisionConfidence);
  const transitionLabel = supportTransitionBadge
    ? "Support Transition Active"
    : resistanceTransitionBadge
      ? "Resistance Transition Active"
      : null;

  const gates = resolveGatesMobile({
    trapPct: trapProbability,
    spot,
    support,
    resistance,
    readinessScore,
    decisionConfidence,
  });
  const passedGates = gates.filter((g) => g.status === "pass").length;
  const allPassed = passedGates === gates.length && gates.length > 0;

  const actionLabel =
    String(tradeAction || "").toUpperCase() === "WAIT" && String(sessionPhase || "").trim()
      ? `${tradeAction} — ${sessionPhase}`
      : tradeAction || "WAIT";
  const dominantMessage =
    blockingReason !== "NONE"
      ? `${friendlyBlockingReason(blockingReason)} — ${tradeAction || "WAIT"}`
      : resolvedReason || "Trap risk elevated. Market still lacks confirmed directional expansion.";

  return (
    <section className="mx-3 rounded-2xl border border-white/10 bg-[#111e2c] px-4 py-4">
      <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.07em] text-slate-600">Trade signal</div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className={`text-[20px] font-semibold tracking-[0.02em] ${actionTone(tradeAction)}`}>{actionLabel}</div>
        <div className={`rounded-full border px-3 py-1 text-[11px] font-medium ${badgeTone(tradeAction)}`}>
          {typeof readinessScore === "number" ? `${Math.round(readinessScore)}% ${readinessState}` : readinessState || "-"}
        </div>
      </div>
      <div className="mb-3 text-[12px] leading-6 text-slate-400">
        {dominantMessage}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
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
        <div className="absolute left-[60%] top-[-5px] h-[15px] w-[1.5px] rounded bg-amber-300">
          <div className="absolute left-1/2 top-[-12px] -translate-x-1/2 whitespace-nowrap font-mono text-[9px] text-amber-300">
            60 entry
          </div>
        </div>
      </div>
      {readinessExplainability ? (
        <div className="ia-readiness-explain ia-readiness-explain-mobile">{readinessExplainability}</div>
      ) : null}

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

      {/* Unlock gates — compact mobile version */}
      {gates.length > 0 ? (
        <div className={`mb-3 rounded-xl border px-3 py-3 ${
          allPassed
            ? "border-emerald-400/20 bg-emerald-400/6"
            : "border-amber-300/15 bg-amber-300/5"
        }`}>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-medium uppercase tracking-[0.07em] text-slate-500">
              Unlock gates
            </span>
            <span className={`text-[11px] font-semibold ${
              allPassed ? "text-emerald-300" : "text-amber-200"
            }`}>
              {passedGates}/{gates.length} cleared
            </span>
          </div>
          <div className="space-y-1.5">
            {gates.map((g) => (
              <div key={g.key} className="flex items-baseline justify-between gap-2">
                <div className="flex min-w-0 items-baseline gap-1.5">
                  <span className={`shrink-0 text-[11px] font-bold ${
                    g.status === "pass"
                      ? "text-emerald-400"
                      : g.status === "near"
                        ? "text-amber-300"
                        : "text-rose-400"
                  }`}>
                    {g.status === "pass" ? "✓" : "✗"}
                  </span>
                  <span className="text-[11px] leading-4 text-slate-400">{g.label}</span>
                </div>
                <div className="flex shrink-0 items-baseline gap-1.5 text-right">
                  <span className={`font-mono text-[11px] font-semibold ${
                    g.status === "pass"
                      ? "text-emerald-300"
                      : g.status === "near"
                        ? "text-amber-200"
                        : "text-rose-300"
                  }`}>
                    {g.current}
                  </span>
                  {g.gap ? (
                    <span className="text-[10px] italic text-slate-500">{g.gap}</span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

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

    </section>
  );
}
