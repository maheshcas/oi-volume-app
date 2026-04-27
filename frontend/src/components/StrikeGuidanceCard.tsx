import type { FC } from "react";

type SuggestedStrike = {
  strike: number;
  delta: number;
  gamma: number;
  theta: number;
  iv: number;
  ltp: number;
  moneyness: string;
  distance_from_spot: number;
};

type StrikeGuidanceProps = {
  recommended_action: string;
  option_type: string;
  suggested_strikes: SuggestedStrike[];
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
  blocking_reason?: string | null;
  trap_probability?: number | null;
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
    iv_skew_magnitude?: number | null;
    straddle_trend?: string;
    atm_straddle_premium?: number | null;
    atm_strike?: number | null;
    iv_percentile?: number | null;
    ce_wall_holding?: boolean;
    pe_wall_holding?: boolean;
  } | null;
  spot?: number | null;
  chainGreeks?: Array<{
    strike: number;
    ce?: { delta?: number; gamma?: number; theta?: number; vega?: number; iv?: number };
    pe?: { delta?: number; gamma?: number; theta?: number; vega?: number; iv?: number };
  }> | null;
};

function formatNumber(v: number | null | undefined) {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function compactValue(value?: string | null, fallback = "-") {
  const text = String(value || "").trim();
  return text ? text : fallback;
}

function extractTrapPct(warnings: string[]): number | null {
  for (const warning of warnings) {
    const m = warning.match(/trap risk\s*(\d+)%/i);
    if (m) return Number(m[1]);
  }
  return null;
}

function parsePremiumFromRrNote(note?: string | null): number | null {
  const text = String(note || "");
  const m = text.match(/(?:₹|â‚¹|Rs)\s*([0-9]+(?:\.[0-9]+)?)/i);
  if (!m) return null;
  return Number(m[1]);
}

function signalBadgeText(signal?: string, action?: string, option?: string) {
  const code = String(signal || "").trim().toUpperCase();
  if (!code || code === "WAIT_NO_SETUP") return "Wait · no clean setup";
  const side = String(action || "").trim().toUpperCase();
  const opt = String(option || "").trim().toUpperCase();
  const pretty = code
    .replace(/^BUY_/, "")
    .replace(/^SELL_/, "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return `${side || "Wait"}${opt ? ` ${opt}` : ""} · ${pretty}`;
}

function thetaSeverity(days_to_expiry: number, theta_warning: boolean): {
  label: string;
  tone: "severe" | "elevated" | "normal";
} {
  if (days_to_expiry <= 0) return { label: "Severe", tone: "severe" };
  if (days_to_expiry <= 1 || theta_warning) return { label: "Elevated", tone: "elevated" };
  return { label: "Normal", tone: "normal" };
}

function fmtNumber(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "-";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

type AtmGreeks = {
  gammaCe?: number;
  gammaPe?: number;
  thetaCe?: number;
  thetaPe?: number;
  vegaCe?: number;
  vegaPe?: number;
};

function resolveAtmGreeks(
  chainGreeks: StrikeGuidanceProps["chainGreeks"],
  atmStrike: number | null | undefined,
): AtmGreeks | null {
  if (!chainGreeks || !Array.isArray(chainGreeks) || chainGreeks.length === 0) return null;
  if (!atmStrike || !Number.isFinite(Number(atmStrike))) return null;
  const row = chainGreeks.find((r) => Math.abs(Number(r.strike) - Number(atmStrike)) < 1);
  if (!row) return null;
  return {
    gammaCe: row.ce?.gamma,
    gammaPe: row.pe?.gamma,
    thetaCe: row.ce?.theta,
    thetaPe: row.pe?.theta,
    vegaCe: row.ce?.vega,
    vegaPe: row.pe?.vega,
  };
}

function gammaTone(gamma: number | null | undefined): "high" | "mid" | "low" | null {
  if (gamma === null || gamma === undefined || !Number.isFinite(gamma)) return null;
  const g = Number(gamma);
  if (g >= 0.0015) return "high";
  if (g >= 0.0008) return "mid";
  return "low";
}

function thetaBurnRupees(theta: number | null | undefined): number | null {
  if (theta === null || theta === undefined || !Number.isFinite(theta)) return null;
  return Math.abs(Number(theta));
}

function thetaBurnTone(burn: number | null): "severe" | "elevated" | "normal" | null {
  if (burn === null) return null;
  if (burn >= 50) return "severe";
  if (burn >= 25) return "elevated";
  return "normal";
}

function vegaToString(vega: number | null | undefined): string {
  if (vega === null || vega === undefined || !Number.isFinite(vega)) return "-";
  return `₹${Number(vega).toFixed(1)}`;
}

function chainGreeksRowFor(
  chainGreeks: StrikeGuidanceProps["chainGreeks"],
  strike: number,
): { vegaCe?: number; vegaPe?: number } | null {
  if (!chainGreeks || !Array.isArray(chainGreeks)) return null;
  const row = chainGreeks.find((r) => Math.abs(Number(r.strike) - Number(strike)) < 1);
  if (!row) return null;
  return { vegaCe: row.ce?.vega, vegaPe: row.pe?.vega };
}

function ivTone(rank: number): "low" | "mid" | "high" {
  if (rank <= 30) return "low";
  if (rank >= 70) return "high";
  return "mid";
}

const StrikeGuidanceCard: FC<StrikeGuidanceProps> = ({
  recommended_action,
  option_type,
  suggested_strikes,
  warnings,
  theta_warning,
  days_to_expiry,
  iv_rank,
  iv_context,
  risk_reward_note,
  selling_favoured,
  position_size_fraction,
  position_size_label,
  execution_layer,
  delta_guidance,
  avoid_buying_premium,
  entry_zone,
  stop_zone,
  target_zone,
  trap_probability,
  strikeIntelligence,
  spot,
  chainGreeks,
}) => {
  const intelAction = String(strikeIntelligence?.recommended_action || "").toUpperCase();
  const intelOption = String(strikeIntelligence?.recommended_option || option_type || "").toUpperCase();
  const intelSignal = String(strikeIntelligence?.entry_signal || "");
  const displayReason = compactValue(strikeIntelligence?.entry_signal_reason, "");
  const isBuySignal = intelAction === "BUY";
  const isSellSignal = intelAction === "SELL";
  const isWaitSignal = !isBuySignal && !isSellSignal;
  const actionBadgeLabel = signalBadgeText(intelSignal, intelAction, intelOption);
  const clampedIvRank =
    iv_rank === null || iv_rank === undefined
      ? null
      : Math.max(0, Math.min(100, iv_rank));
  const ivHistoryBuilding = String(iv_context || "").toLowerCase().includes("insufficient");
  const actionUpper = String(recommended_action || "").toUpperCase();
  const executionTitle =
    actionUpper.includes("SELL OTM CE")
      ? "Execution Zones (CE sell setup):"
      : actionUpper.includes("SELL OTM PE")
        ? "Execution Zones (PE sell setup):"
        : "Execution Zones:";
  const executionContext = `For ${recommended_action || "-"} · Underlying price reference`;
  const trapPct = extractTrapPct(warnings);
  const filteredSuggestedStrikes = suggested_strikes.filter(
    (s) => Number(s.ltp || 0) >= 1 && Math.abs(Number(s.delta || 0)) >= 0.01,
  );
  const rrPremium = parsePremiumFromRrNote(risk_reward_note);
  const hasLivePremiumStrike = suggested_strikes.some((s) => Number(s.ltp || 0) >= 1);
  const showRrNote =
    Boolean(risk_reward_note) &&
    hasLivePremiumStrike &&
    (rrPremium === null || rrPremium >= 1);
  const showNoPremiumNote = !showRrNote && suggested_strikes.some((s) => Number(s.ltp || 0) < 1);
  const waitSignal = intelSignal.toUpperCase() === "WAIT_NO_SETUP";
  const trapProbabilityValue =
    typeof trap_probability === "number" && Number.isFinite(trap_probability)
      ? Math.round(trap_probability)
      : 0;
  void selling_favoured;

  const spotNum =
    typeof spot === "number" && Number.isFinite(spot) ? spot : null;
  const atmStraddle =
    typeof strikeIntelligence?.atm_straddle_premium === "number" &&
    Number.isFinite(strikeIntelligence.atm_straddle_premium)
      ? Number(strikeIntelligence.atm_straddle_premium)
      : null;
  const breakevenLower =
    spotNum !== null && atmStraddle !== null ? spotNum - atmStraddle : null;
  const breakevenUpper =
    spotNum !== null && atmStraddle !== null ? spotNum + atmStraddle : null;
  const atmGreeks = resolveAtmGreeks(chainGreeks ?? null, strikeIntelligence?.atm_strike);
  const atmGammaCe = atmGreeks?.gammaCe;
  const atmThetaCe = atmGreeks?.thetaCe;
  const atmThetaPe = atmGreeks?.thetaPe;
  const atmThetaAvg =
    atmThetaCe !== undefined && atmThetaPe !== undefined
      ? (Number(atmThetaCe) + Number(atmThetaPe)) / 2
      : atmThetaCe !== undefined
        ? Number(atmThetaCe)
        : atmThetaPe !== undefined
          ? Number(atmThetaPe)
          : null;
  const thetaBurn = thetaBurnRupees(atmThetaAvg);
  const thetaBurnToneValue = thetaBurnTone(thetaBurn);
  const gammaToneValue = gammaTone(atmGammaCe);
  const ivPercentile =
    typeof strikeIntelligence?.iv_percentile === "number" &&
    Number.isFinite(strikeIntelligence.iv_percentile)
      ? Math.max(0, Math.min(100, Number(strikeIntelligence.iv_percentile)))
      : null;

  // Build the one-line subtitle that explains the state
  const stateSubtitle = (() => {
    if (isWaitSignal) {
      const parts: string[] = [];
      if (avoid_buying_premium) parts.push("Premium buying locked");
      if (trapProbabilityValue >= 55) parts.push(`Trap ${trapProbabilityValue}% blocking signals`);
      if (displayReason) parts.push(displayReason);
      else if (parts.length === 0) parts.push("No directional conviction yet");
      return parts.join(" · ");
    }
    return displayReason || "Signal active · review zones below";
  })();

  const theta = thetaSeverity(days_to_expiry, theta_warning);
  const ivRankTone = clampedIvRank !== null ? ivTone(clampedIvRank) : null;

  return (
    <div className="ia-card strike-guidance-card sgc-v2">
      {/* Tier 1: Header — muted label + state */}
      <div className="sgc-v2-header">
        <div className="sgc-v2-eyebrow">Strike Guidance</div>
        <div className="sgc-v2-expiry-meta">
          {days_to_expiry}d to expiry
          {theta.tone !== "normal" ? (
            <span className={`sgc-v2-theta-tag sgc-v2-theta-${theta.tone}`}>Theta {theta.label}</span>
          ) : null}
        </div>
      </div>

      <div className={`sgc-v2-state sgc-v2-state-${isBuySignal ? "buy" : isSellSignal ? "sell" : "wait"}`}>
        <span className="sgc-v2-state-dot" />
        <span className="sgc-v2-state-label">{actionBadgeLabel}</span>
      </div>

      <div className="sgc-v2-subtitle">{stateSubtitle}</div>

      {/* Tier 2: Unlock block (WAIT state) OR Execution block (active signal) */}
      {waitSignal ? (
        <div className="sgc-v2-unlock">
          <div className="sgc-v2-unlock-label">Unlock when</div>
          <div className="sgc-v2-unlock-body">
            {trapProbabilityValue >= 55
              ? `Trap drops below 55% · currently ${trapProbabilityValue}%`
              : "Spot approaches support or resistance edge"}
          </div>
        </div>
      ) : (entry_zone || stop_zone || target_zone || delta_guidance || strikeIntelligence?.stop_description || strikeIntelligence?.target_description) ? (
        <div className="sgc-v2-exec">
          <div className="sgc-v2-exec-label">{executionTitle}</div>
          <div className="sgc-v2-exec-context">{executionContext}</div>
          <div className="sgc-v2-exec-grid">
            <div className="sgc-v2-exec-item">
              <span className="sgc-v2-exec-key">Delta</span>
              <span className="sgc-v2-exec-val">
                {strikeIntelligence?.delta_target_min != null && strikeIntelligence?.delta_target_max != null
                  ? `${Number(strikeIntelligence.delta_target_min).toFixed(2)}–${Number(strikeIntelligence.delta_target_max).toFixed(2)} ${isBuySignal ? "(directional)" : isSellSignal ? "(OTM)" : ""}`
                  : compactValue(delta_guidance, execution_layer || "-")}
              </span>
            </div>
            <div className="sgc-v2-exec-item">
              <span className="sgc-v2-exec-key">Stop</span>
              <span className="sgc-v2-exec-val">{compactValue(strikeIntelligence?.stop_description, compactValue(stop_zone))}</span>
            </div>
            <div className="sgc-v2-exec-item">
              <span className="sgc-v2-exec-key">Target</span>
              <span className="sgc-v2-exec-val">{compactValue(strikeIntelligence?.target_description, compactValue(target_zone))}</span>
            </div>
          </div>
        </div>
      ) : null}

      {/* Tier 3: Metric chips — context at a glance */}
      <div className="sgc-v2-chips">
        <div className="sgc-v2-chip">
          <span className="sgc-v2-chip-label">Options cost</span>
          <span className={`sgc-v2-chip-value ${ivRankTone ? `sgc-v2-iv-${ivRankTone}` : ""}`}>
            {clampedIvRank !== null && !ivHistoryBuilding
              ? clampedIvRank <= 30
                ? `Cheap (${clampedIvRank.toFixed(0)}%)`
                : clampedIvRank >= 70
                  ? `Expensive (${clampedIvRank.toFixed(0)}%)`
                  : `Normal (${clampedIvRank.toFixed(0)}%)`
              : ivHistoryBuilding
                ? "Building"
                : "-"}
          </span>
        </div>
        <div className="sgc-v2-chip">
          <span className="sgc-v2-chip-label">Expiry target</span>
          <span className="sgc-v2-chip-value sgc-v2-chip-maxpain">
            {strikeIntelligence?.max_pain_strike != null
              ? `${formatNumber(strikeIntelligence.max_pain_strike)} · writers want it here`
              : "-"}
          </span>
        </div>
        <div className="sgc-v2-chip">
          <span className="sgc-v2-chip-label">Move needed</span>
          <span className="sgc-v2-chip-value">
            {strikeIntelligence?.atm_straddle_premium != null
              ? `±${Number(strikeIntelligence.atm_straddle_premium).toFixed(0)}pts to profit`
              : "-"}
          </span>
        </div>
        <div className="sgc-v2-chip">
          <span className="sgc-v2-chip-label">Options bias</span>
          <span className="sgc-v2-chip-value">
            {(() => {
              const skew = String(strikeIntelligence?.iv_skew || "").toLowerCase();
              if (skew.includes("call") || skew.includes("ce") || skew.includes("bear")) return "CE pricier · market fears drop";
              if (skew.includes("put") || skew.includes("pe") || skew.includes("bull")) return "PE pricier · market fears rise";
              if (skew === "neutral" || skew === "") return "Balanced · no side favoured";
              return compactValue(strikeIntelligence?.iv_skew, "-");
            })()}
          </span>
        </div>
      </div>

      {(breakevenLower !== null || thetaBurn !== null || gammaToneValue !== null || ivPercentile !== null) ? (
        <div className="sgc-v2-greeks">
          <div className="sgc-v2-greeks-head">
            <span className="sgc-v2-greeks-label">Options market reading</span>
            <span className="sgc-v2-greeks-tag">ATM strike</span>
          </div>

          {breakevenLower !== null && breakevenUpper !== null && atmStraddle !== null ? (
            <div className="sgc-v2-breakeven">
              <div className="sgc-v2-breakeven-hero">
                Price needs to move <strong>±{Math.round(atmStraddle)}pts</strong> for straddle buyers to profit
              </div>
              <div className="sgc-v2-breakeven-row">
                <span className="sgc-v2-breakeven-label">Safe zone</span>
                <span className="sgc-v2-breakeven-range">
                  {fmtNumber(breakevenLower)} – {fmtNumber(breakevenUpper)}
                </span>
              </div>
              <div className="sgc-v2-breakeven-track-wrap">
                <div className="sgc-v2-breakeven-track">
                  <div className="sgc-v2-breakeven-fill" />
                </div>
              </div>
              <div className="sgc-v2-breakeven-sub">
                Straddle writers profit if price stays inside this band
              </div>
            </div>
          ) : null}

          <div className="sgc-v2-greeks-grid">
            {gammaToneValue ? (
              <div className={`sgc-v2-greek-cell sgc-v2-greek-cell-${gammaToneValue}`}>
                <span className="sgc-v2-greek-key">Premium sensitivity</span>
                <span className="sgc-v2-greek-val">
                  {gammaToneValue === "high" ? "Sharp" : gammaToneValue === "mid" ? "Normal" : "Slow"}
                </span>
                <span className="sgc-v2-greek-sub">
                  {gammaToneValue === "high"
                    ? "₹50 spot move → big premium swing"
                    : gammaToneValue === "mid"
                      ? "₹50 spot move → normal premium swing"
                      : "₹50 spot move → small premium change"}
                </span>
              </div>
            ) : null}

            {thetaBurn !== null && thetaBurnToneValue ? (
              <div className={`sgc-v2-greek-cell sgc-v2-greek-cell-${thetaBurnToneValue}`}>
                <span className="sgc-v2-greek-key">Daily time cost</span>
                <span className="sgc-v2-greek-val">₹{Math.round(thetaBurn)}/day</span>
                <span className="sgc-v2-greek-sub">
                  {thetaBurnToneValue === "severe"
                    ? "heavy · option loses this per day"
                    : thetaBurnToneValue === "elevated"
                      ? "option loses this per day — watch"
                      : "low · time is not a big factor"}
                </span>
              </div>
            ) : null}

            {ivPercentile !== null ? (
              <div
                className={`sgc-v2-greek-cell sgc-v2-greek-cell-${
                  ivPercentile >= 70 ? "high" : ivPercentile <= 30 ? "low" : "mid"
                }`}
              >
                <span className="sgc-v2-greek-key">Options vs history</span>
                <span className="sgc-v2-greek-val">{ivPercentile.toFixed(0)}%</span>
                <span className="sgc-v2-greek-sub">
                  {ivPercentile >= 70
                    ? `pricier than ${ivPercentile.toFixed(0)}% of past sessions`
                    : ivPercentile <= 30
                      ? `cheaper than ${(100 - ivPercentile).toFixed(0)}% of past sessions`
                      : `mid-range · ${(100 - ivPercentile).toFixed(0)}% of past sessions were costlier`}
                </span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Tier 4: Suggested strikes table (active signal only) */}
      {!waitSignal &&
        suggested_strikes.some((s) => Number(s.ltp || 0) >= 1) &&
        filteredSuggestedStrikes.length > 0 && (
          <div className="sgc-strikes">
            <div className="sgc-strikes-header sgc-strikes-header-v2">
              <span>Strike</span>
              <span>Delta</span>
              <span>Gamma</span>
              <span>Theta/d</span>
              <span>Vega</span>
              <span>LTP</span>
            </div>
            {filteredSuggestedStrikes.map((s, idx) => (
              <div
                key={s.strike}
                className={`sgc-strike-row sgc-strike-row-v2${idx === Math.floor(filteredSuggestedStrikes.length / 2) ? " sgc-strike-best" : ""}`}
              >
                <span className="sgc-strike-val">
                  {formatNumber(s.strike)} {option_type}
                  <span className="sgc-moneyness">
                    {s.moneyness}
                    {s.distance_from_spot != null
                      ? ` • ${Math.round(s.distance_from_spot)}pts`
                      : ""}
                  </span>
                  <span className="sgc-delta-pnl">
                    <span className="sgc-delta-pnl-up">+1pt → +₹{s.delta?.toFixed(2)}</span>
                    &nbsp;|&nbsp;
                    <span className="sgc-delta-pnl-dn">-1pt → -₹{s.delta?.toFixed(2)}</span>
                  </span>
                </span>
                <span>{s.delta.toFixed(2)}</span>
                <span>{Number.isFinite(s.gamma) ? s.gamma.toFixed(4) : "-"}</span>
                <span className="sgc-theta">₹{Math.abs(s.theta).toFixed(1)}</span>
                <span className="sgc-vega">
                  {(() => {
                    const row = chainGreeksRowFor(chainGreeks ?? null, s.strike);
                    const vega =
                      option_type === "CE" ? row?.vegaCe : row?.vegaPe;
                    return vegaToString(vega);
                  })()}
                </span>
                <span>₹{s.ltp.toFixed(1)}</span>
              </div>
            ))}
          </div>
        )}

      {showRrNote && <div className="sgc-rr-note">{risk_reward_note}</div>}
      {showNoPremiumNote && <div className="sgc-rr-note">Strike at expiry — no premium</div>}

      {/* Footer: size/layer context — only shown when relevant */}
      {(execution_layer || position_size_label || trapPct !== null) && (
        <div className="sgc-v2-footer">
          {execution_layer ? <span>Layer: {execution_layer}</span> : null}
          {position_size_label ? (
            <span>
              Size: {position_size_label}
              {typeof position_size_fraction === "number" ? ` (${Math.round(position_size_fraction * 100)}%)` : ""}
            </span>
          ) : null}
          {trapPct !== null ? <span>Trap {trapPct}%</span> : null}
        </div>
      )}
    </div>
  );
};

export default StrikeGuidanceCard;
