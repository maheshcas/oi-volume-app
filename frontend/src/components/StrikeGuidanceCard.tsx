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
  if (!code || code === "WAIT_NO_SETUP") return "WAIT - No Clean Setup";
  const side = String(action || "").trim().toUpperCase();
  const opt = String(option || "").trim().toUpperCase();
  const pretty = code
    .replace(/^BUY_/, "")
    .replace(/^SELL_/, "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return `${side || "WAIT"}${opt ? ` ${opt}` : ""} - ${pretty}`;
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
  strikeIntelligence,
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
  const actionableReason =
    isWaitSignal && clampedIvRank !== null && clampedIvRank <= 30
      ? `IV low (${clampedIvRank.toFixed(0)}%) - premium cheap · No clean setup${trapPct !== null ? ` · Trap ${trapPct}%` : ""}`
      : displayReason;
  const rrPremium = parsePremiumFromRrNote(risk_reward_note);
  const hasLivePremiumStrike = suggested_strikes.some((s) => Number(s.ltp || 0) >= 1);
  const showRrNote =
    Boolean(risk_reward_note) &&
    hasLivePremiumStrike &&
    (rrPremium === null || rrPremium >= 1);
  const showNoPremiumNote = !showRrNote && suggested_strikes.some((s) => Number(s.ltp || 0) < 1);
  void selling_favoured;

  return (
    <div className="ia-card strike-guidance-card">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Strike Guidance</h3>
        <span className={`sgc-action-badge ${isBuySignal ? "sgc-signal-buy" : isWaitSignal ? "sgc-signal-wait" : "sgc-signal-sell"}`}>
          {actionBadgeLabel}
        </span>
      </div>
      {actionableReason ? <div className="sgc-entry-reason">{actionableReason}</div> : null}

      {clampedIvRank !== null && !ivHistoryBuilding && (
        <div className="sgc-iv-row">
          <div className="sgc-iv-bar-wrap">
            <div
              className="sgc-iv-bar"
              style={{
                width: `${Math.max(2, Math.min(100, clampedIvRank))}%`,
                background: clampedIvRank >= 70 ? "#ef4444" : clampedIvRank <= 30 ? "#22c55e" : "#f59e0b",
              }}
            />
          </div>
          <span className="sgc-iv-label">IV Rank {clampedIvRank.toFixed(0)}%</span>
          <span className="sgc-iv-context">{iv_context}</span>
        </div>
      )}
      {ivHistoryBuilding && (
        <div className="sgc-iv-row sgc-iv-row-building">
          <span className="sgc-iv-label">IV Rank -</span>
          <span className="sgc-iv-context">Building...</span>
        </div>
      )}

      <div className="sgc-meta-row">
        <span className={`sgc-expiry ${theta_warning ? "sgc-expiry-warn" : ""}`}>
          {days_to_expiry}d to expiry
          {theta_warning ? " - theta risk" : ""}
        </span>
      </div>
      <div className="sgc-meta-row sgc-meta-grid">
        <span className="sgc-meta-chip">Layer: {execution_layer || "-"}</span>
        <span className="sgc-meta-chip">
          Size: {position_size_label || "-"}
          {typeof position_size_fraction === "number" ? ` (${Math.round(position_size_fraction * 100)}%)` : ""}
        </span>
      </div>
      {avoid_buying_premium ? (
        <div className="sgc-lock-indicator">Premium buy lock active</div>
      ) : null}
      {(entry_zone || stop_zone || target_zone || delta_guidance || execution_layer || strikeIntelligence?.stop_description || strikeIntelligence?.target_description) ? (
        <div className="sgc-trade-strip">
          <div className="sgc-trade-strip-title">{executionTitle}</div>
          <div className="sgc-trade-strip-context">{executionContext}</div>
          <div className="sgc-trade-grid">
            <div className="sgc-trade-item">
              <span className="sgc-trade-label">Delta</span>
              <span className="sgc-trade-value">
                {strikeIntelligence?.delta_target_min != null && strikeIntelligence?.delta_target_max != null
                  ? `Delta ${Number(strikeIntelligence.delta_target_min).toFixed(2)}-${Number(strikeIntelligence.delta_target_max).toFixed(2)} ${isBuySignal ? "(directional)" : isSellSignal ? "(OTM)" : ""}`
                  : compactValue(delta_guidance, execution_layer || "-")}
              </span>
            </div>
            <div className="sgc-trade-item">
              <span className="sgc-trade-label">Stop</span>
              <span className="sgc-trade-value">{compactValue(strikeIntelligence?.stop_description, compactValue(stop_zone))}</span>
            </div>
            <div className="sgc-trade-item">
              <span className="sgc-trade-label">Target</span>
              <span className="sgc-trade-value">{compactValue(strikeIntelligence?.target_description, compactValue(target_zone))}</span>
            </div>
          </div>
        </div>
      ) : null}

      {filteredSuggestedStrikes.length > 0 && (
        <div className="sgc-strikes">
          <div className="sgc-strikes-header">
            <span>Strike</span>
            <span>Delta</span>
            <span>Gamma</span>
            <span>Theta/day</span>
            <span>LTP</span>
          </div>
          {filteredSuggestedStrikes.map((s, idx) => (
            <div
              key={s.strike}
              className={`sgc-strike-row${idx === Math.floor(filteredSuggestedStrikes.length / 2) ? " sgc-strike-best" : ""}`}
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
                  <span className="sgc-delta-pnl-up">+1pt -&gt; +₹{s.delta?.toFixed(2)}</span>
                  &nbsp;|&nbsp;
                  <span className="sgc-delta-pnl-dn">-1pt -&gt; -₹{s.delta?.toFixed(2)}</span>
                </span>
              </span>
              <span>{s.delta.toFixed(2)}</span>
              <span>{Number.isFinite(s.gamma) ? s.gamma.toFixed(4) : "-"}</span>
              <span className="sgc-theta">₹{Math.abs(s.theta).toFixed(1)}</span>
              <span>₹{s.ltp.toFixed(1)}</span>
            </div>
          ))}
        </div>
      )}

      {showRrNote && <div className="sgc-rr-note">{risk_reward_note}</div>}
      {showNoPremiumNote && <div className="sgc-rr-note">Strike at expiry - no premium</div>}
      <div className="sgc-bottom-info">
        Max pain: {strikeIntelligence?.max_pain_strike != null ? formatNumber(strikeIntelligence.max_pain_strike) : "-"}
        {strikeIntelligence?.max_pain_pull ? ` (${strikeIntelligence.max_pain_pull} pull)` : ""}
        {" | "}
        IV skew: {compactValue(strikeIntelligence?.iv_skew, "-")}
        {" | "}
        Straddle {"₹"}
        {strikeIntelligence?.atm_straddle_premium != null ? Number(strikeIntelligence.atm_straddle_premium).toFixed(1) : "-"}
        {" "}
        {compactValue(strikeIntelligence?.straddle_trend, "-")}
      </div>

      {warnings.length > 0 && (
        <div className="sgc-warnings">
          {warnings.map((w) => (
            <div key={w} className="sgc-warning-item">[!] {w}</div>
          ))}
        </div>
      )}
    </div>
  );
};

export default StrikeGuidanceCard;
