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
};

function formatNumber(v: number | null | undefined) {
  if (v === null || v === undefined) return "-";
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
  const clampedIvRank =
    iv_rank === null || iv_rank === undefined
      ? null
      : Math.max(0, Math.min(100, iv_rank));
  void selling_favoured;

  return (
    <div className="ia-card strike-guidance-card">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Strike Guidance</h3>
        <span className={`sgc-action-badge ${isBuy ? "sgc-buy" : isWait ? "sgc-wait" : "sgc-sell"}`}>
          {recommended_action}
        </span>
      </div>

      {clampedIvRank !== null && (
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

      <div className="sgc-meta-row">
        <span className={`sgc-expiry ${theta_warning ? "sgc-expiry-warn" : ""}`}>
          {days_to_expiry}d to expiry
          {theta_warning ? " - theta risk" : ""}
        </span>
      </div>

      {suggested_strikes.length > 0 && (
        <div className="sgc-strikes">
          <div className="sgc-strikes-header">
            <span>Strike</span>
            <span>Delta</span>
            <span>Gamma</span>
            <span>Theta/day</span>
            <span>LTP</span>
          </div>
          {suggested_strikes.map((s, idx) => (
            <div
              key={s.strike}
              className={`sgc-strike-row${idx === Math.floor(suggested_strikes.length / 2) ? " sgc-strike-best" : ""}`}
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

      {risk_reward_note && <div className="sgc-rr-note">{risk_reward_note}</div>}

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
