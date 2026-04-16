import type { FC } from "react";

type EntryTarget = {
  trade_type?: string;
  entry_underlying?: number | null;
  entry_option_strike?: number | null;
  entry_option_type?: string | null;
  entry_option_action?: string | null;
  entry_premium?: number | null;
  entry_brief?: string;
  stop_underlying?: number | null;
  stop_premium_value?: number | null;
  stop_brief?: string;
  target_1?: number | null;
  target_2?: number | null;
  target_brief?: string;
  rr_t1?: number | null;
  rr_t2?: number | null;
  rr_brief?: string;
  call_wall_used?: number | null;
  put_wall_used?: number | null;
  price_magnet_strike?: number | null;
  magnet_pull_direction?: string | null;
  magnet_distance_pts?: number | null;
  secondary_magnet?: number | null;
  magnet_character?: string | null;
  compression_zone?: boolean;
};

type EntryTargetCardProps = {
  entryTarget: EntryTarget | null | undefined;
};

function fmt(v: number | null | undefined) {
  if (v === null || v === undefined || !Number.isFinite(v)) return "-";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function formatMagnetPull(direction?: string | null, distance?: number | null) {
  const d = typeof distance === "number" && Number.isFinite(distance) ? distance.toFixed(1) : "-";
  if (direction === "up") return `▲ ${d}pts above spot`;
  if (direction === "down") return `▼ ${d}pts below spot`;
  if (direction === "at") return "◉ At spot";
  return "unknown pull";
}

function formatMagnetCharacter(character?: string | null) {
  const c = String(character || "").trim().toLowerCase();
  if (!c) return "-";
  if (c === "resistance" || c === "support" || c === "balanced") return c;
  return c.replace(/[_-]+/g, " ");
}

function getMagnetConflictWarning(
  action?: string | null,
  optionType?: string | null,
  magnetPullDirection?: string | null,
) {
  const act = String(action || "").toUpperCase();
  const opt = String(optionType || "").toUpperCase();
  const pull = String(magnetPullDirection || "").toLowerCase();

  if (act === "SELL" && opt === "CE" && pull === "up") {
    return "Magnet pulling up - trade against magnet, use smaller size";
  }
  if (act === "BUY" && opt === "CE" && pull === "down") {
    return "Magnet pulling down - trade against magnet, use smaller size";
  }
  return null;
}

const EntryTargetCard: FC<EntryTargetCardProps> = ({ entryTarget }) => {
  const tradeType = String(entryTarget?.trade_type || "NONE").toUpperCase();
  if (!entryTarget) return null;

  if (tradeType === "NONE") {
    return (
      <div className="ia-card entry-target-card">
        <div className="ia-card-title-row">
          <h3 className="ia-card-title">Trade Setup</h3>
          <span className="et-action-badge et-badge-neutral">WAIT</span>
        </div>
        <div className="et-entry-brief">
          {entryTarget.entry_brief || "No trade setup currently."}
        </div>
        <div className="et-notes">{entryTarget.stop_brief || "Wait for a clean setup."}</div>
        <div className="et-notes">{entryTarget.target_brief || "No targets while waiting."}</div>

        {entryTarget.price_magnet_strike ? (
          <div className="et-magnet-row">
            <span className="et-label">MAGNET</span>
            <span className={`et-magnet-value et-magnet-${String(entryTarget.magnet_pull_direction || "unknown")}`}>
              {fmt(entryTarget.price_magnet_strike)}
            </span>
            <span className="et-magnet-pull">
              {formatMagnetPull(entryTarget.magnet_pull_direction, entryTarget.magnet_distance_pts)}
            </span>
            <span className="et-magnet-char">{formatMagnetCharacter(entryTarget.magnet_character)}</span>
          </div>
        ) : null}

        {entryTarget.compression_zone && entryTarget.price_magnet_strike && entryTarget.secondary_magnet ? (
          <div className="et-compression-note">
            Compressed between {fmt(entryTarget.price_magnet_strike)} and {fmt(entryTarget.secondary_magnet)}. Price pinned.
          </div>
        ) : null}

        <div className="et-walls">
          CE Wall {fmt(entryTarget.call_wall_used)} | PE Wall {fmt(entryTarget.put_wall_used)}
        </div>
      </div>
    );
  }

  const action = String(entryTarget.entry_option_action || "").toUpperCase();
  const optionType = String(entryTarget.entry_option_type || "").toUpperCase();
  const badgeLabel =
    optionType === "STRADDLE"
      ? "STRADDLE"
      : `${action || "TRADE"} ${optionType || ""}`.trim();
  const badgeClass =
    optionType === "STRADDLE"
      ? "et-badge-straddle"
      : action === "BUY" && optionType === "CE"
        ? "et-badge-buy-ce"
        : action === "BUY" && optionType === "PE"
          ? "et-badge-buy-pe"
          : action === "SELL"
            ? "et-badge-sell"
            : "et-badge-neutral";
  const magnetConflictWarning = getMagnetConflictWarning(
    entryTarget.entry_option_action,
    entryTarget.entry_option_type,
    entryTarget.magnet_pull_direction,
  );

  return (
    <div className="ia-card entry-target-card">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Trade Setup</h3>
        <span className={`et-action-badge ${badgeClass}`}>{badgeLabel}</span>
      </div>

      <div className="et-entry-brief">{entryTarget.entry_brief || "No setup brief available."}</div>

      <div className="et-grid">
        <div className="et-item">
          <span className="et-label">Entry</span>
          <span className="et-value">{fmt(entryTarget.entry_underlying)}</span>
        </div>
        <div className="et-item">
          <span className="et-label">Stop</span>
          <span className="et-value">
            {fmt(entryTarget.stop_underlying)}
            {entryTarget.stop_premium_value != null ? `  Rs ${entryTarget.stop_premium_value.toFixed(1)}` : ""}
          </span>
        </div>
        <div className="et-item">
          <span className="et-label">T1</span>
          <span className="et-value">
            {fmt(entryTarget.target_1)}
            {entryTarget.rr_t1 != null ? ` (${entryTarget.rr_t1.toFixed(1)}x RR)` : ""}
          </span>
        </div>
        <div className="et-item">
          <span className="et-label">T2</span>
          <span className="et-value">
            {fmt(entryTarget.target_2)}
            {entryTarget.rr_t2 != null ? ` (${entryTarget.rr_t2.toFixed(1)}x RR)` : ""}
          </span>
        </div>
      </div>

      <div className="et-notes">{entryTarget.stop_brief || "-"}</div>
      <div className="et-notes">{entryTarget.target_brief || entryTarget.rr_brief || "-"}</div>

      {entryTarget.price_magnet_strike ? (
        <div className="et-magnet-row">
          <span className="et-label">MAGNET</span>
          <span className={`et-magnet-value et-magnet-${String(entryTarget.magnet_pull_direction || "unknown")}`}>
            {fmt(entryTarget.price_magnet_strike)}
          </span>
          <span className="et-magnet-pull">
            {formatMagnetPull(entryTarget.magnet_pull_direction, entryTarget.magnet_distance_pts)}
          </span>
          <span className="et-magnet-char">{formatMagnetCharacter(entryTarget.magnet_character)}</span>
        </div>
      ) : null}

      {magnetConflictWarning ? (
        <div className="et-magnet-warning">{magnetConflictWarning}</div>
      ) : null}

      {entryTarget.compression_zone && entryTarget.price_magnet_strike && entryTarget.secondary_magnet ? (
        <div className="et-compression-note">
          Compressed between {fmt(entryTarget.price_magnet_strike)} and {fmt(entryTarget.secondary_magnet)}. Price pinned.
        </div>
      ) : null}

      <div className="et-walls">
        CE Wall {fmt(entryTarget.call_wall_used)} | PE Wall {fmt(entryTarget.put_wall_used)}
      </div>
    </div>
  );
};

export default EntryTargetCard;
