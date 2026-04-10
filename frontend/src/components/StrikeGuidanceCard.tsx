import type { FC } from "react";

type SuggestedStrike = {
  strike: number;
  delta: number;
  theta: number;
  iv: number;
  ltp: number;
  moneyness: string;
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
};

function formatNumber(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
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
}) => {
  const isBuy = recommended_action.toLowerCase().startsWith("buy");
  const isWait = recommended_action.toLowerCase().startsWith("wait");
  void selling_favoured;

  return (
    <div className="ia-card strike-guidance-card">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Strike Guidance</h3>
        <span className={`sgc-action-badge ${isBuy ? "sgc-buy" : isWait ? "sgc-wait" : "sgc-sell"}`}>
          {recommended_action}
        </span>
      </div>

      {/* IV Context */}
      {iv_rank !== null && iv_rank !== undefined && (
        <div className="sgc-iv-row">
          <div className="sgc-iv-bar-wrap">
            <div
              className="sgc-iv-bar"
              style={{
                width: `${Math.min(100, iv_rank)}%`,
                background: iv_rank >= 70 ? "#ef4444" : iv_rank <= 30 ? "#22c55e" : "#f59e0b",
              }}
            />
          </div>
          <span className="sgc-iv-label">IV Rank {iv_rank.toFixed(0)}%</span>
          <span className="sgc-iv-context">{iv_context}</span>
        </div>
      )}

      {/* Expiry */}
      <div className="sgc-meta-row">
        <span className={`sgc-expiry ${theta_warning ? "sgc-expiry-warn" : ""}`}>
          {days_to_expiry}d to expiry
          {theta_warning ? " — theta risk" : ""}
        </span>
      </div>

      {/* Suggested strikes */}
      {suggested_strikes.length > 0 && (
        <div className="sgc-strikes">
          <div className="sgc-strikes-header">
            <span>Strike</span>
            <span>Delta</span>
            <span>Theta/day</span>
            <span>IV%</span>
            <span>LTP</span>
          </div>
          {suggested_strikes.map((s) => (
            <div key={s.strike} className="sgc-strike-row">
              <span className="sgc-strike-val">
                {formatNumber(s.strike)} {option_type}
                <span className="sgc-moneyness">{s.moneyness}</span>
              </span>
              <span>{s.delta.toFixed(2)}</span>
              <span className="sgc-theta">₹{Math.abs(s.theta).toFixed(1)}</span>
              <span>{s.iv.toFixed(1)}%</span>
              <span>₹{s.ltp.toFixed(1)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Risk/reward note */}
      {risk_reward_note && <div className="sgc-rr-note">{risk_reward_note}</div>}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="sgc-warnings">
          {warnings.map((w) => (
            <div key={w} className="sgc-warning-item">⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  );
};

export default StrikeGuidanceCard;
