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
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function magnetInline(
  direction?: string | null,
  distance?: number | null,
  character?: string | null,
) {
  const d =
    typeof distance === "number" && Number.isFinite(distance)
      ? Math.round(distance)
      : null;
  const dir = String(direction || "").toLowerCase();
  const rawCharacter = String(character || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, "_");
  const charLabelMap: Record<string, string> = {
    strong_support: "Strong support magnet",
    support: "Support magnet",
    balanced: "Neutral magnet",
    resistance: "Resistance magnet",
    strong_resistance: "Strong resistance magnet",
  };
  const charText =
    charLabelMap[rawCharacter] ??
    String(character || "")
      .trim()
      .toLowerCase()
      .replace(/[_-]+/g, " ");
  const arrow = dir === "up" ? "↑" : dir === "down" ? "↓" : dir === "at" ? "◉" : "";
  const parts: string[] = [];
  if (arrow && d !== null) parts.push(`${arrow} ${d}pts`);
  if (charText) parts.push(charText);
  return parts.length > 0 ? parts.join(" · ") : "—";
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
    return "Magnet pulling up — trade against magnet, use smaller size";
  }
  if (act === "BUY" && opt === "CE" && pull === "down") {
    return "Magnet pulling down — trade against magnet, use smaller size";
  }
  return null;
}

const EntryTargetCard: FC<EntryTargetCardProps> = ({ entryTarget }) => {
  if (!entryTarget) return null;
  const tradeType = String(entryTarget.trade_type || "NONE").toUpperCase();
  const isWait = tradeType === "NONE";

  const action = String(entryTarget.entry_option_action || "").toUpperCase();
  const optionType = String(entryTarget.entry_option_type || "").toUpperCase();

  const stateTone: "standby" | "buy" | "sell" | "straddle" = isWait
    ? "standby"
    : optionType === "STRADDLE"
      ? "straddle"
      : action === "BUY" && optionType === "CE"
        ? "buy"
        : action === "BUY" && optionType === "PE"
          ? "sell"
          : action === "SELL"
            ? "sell"
            : "standby";

  const stateLabel = isWait
    ? "Standby"
    : optionType === "STRADDLE"
      ? "Straddle"
      : `${action === "BUY" ? "Buy" : action === "SELL" ? "Sell" : "Trade"} ${optionType || ""}`.trim();

  const subtitle = isWait
    ? "Waiting for clean directional signal · no active position."
    : entryTarget.entry_brief || "Signal active · review zones below.";

  const magnetConflictWarning = !isWait
    ? getMagnetConflictWarning(
        entryTarget.entry_option_action,
        entryTarget.entry_option_type,
        entryTarget.magnet_pull_direction,
      )
    : null;

  const magnetSub = magnetInline(
    entryTarget.magnet_pull_direction,
    entryTarget.magnet_distance_pts,
    entryTarget.magnet_character,
  );

  const cells: Array<{
    key: string;
    label: string;
    value: string;
    subValue?: string;
    empty: boolean;
  }> = [
    {
      key: "entry",
      label: "Entry",
      value: fmt(entryTarget.entry_underlying),
      empty: !Number.isFinite(Number(entryTarget.entry_underlying)),
    },
    {
      key: "stop",
      label: "Stop",
      value: fmt(entryTarget.stop_underlying),
      subValue:
        entryTarget.stop_premium_value != null
          ? `₹${Number(entryTarget.stop_premium_value).toFixed(1)}`
          : undefined,
      empty: !Number.isFinite(Number(entryTarget.stop_underlying)),
    },
    {
      key: "t1",
      label: "T1",
      value: fmt(entryTarget.target_1),
      subValue:
        entryTarget.rr_t1 != null ? `${entryTarget.rr_t1.toFixed(1)}× RR` : undefined,
      empty: !Number.isFinite(Number(entryTarget.target_1)),
    },
    {
      key: "t2",
      label: "T2",
      value: fmt(entryTarget.target_2),
      subValue:
        entryTarget.rr_t2 != null ? `${entryTarget.rr_t2.toFixed(1)}× RR` : undefined,
      empty: !Number.isFinite(Number(entryTarget.target_2)),
    },
  ];

  return (
    <div className="ia-card entry-target-card et-v2">
      <div className="et-v2-header">
        <div className="et-v2-eyebrow">Trade Setup</div>
        <div className={`et-v2-state et-v2-state-${stateTone}`}>
          <span className="et-v2-state-dot" />
          <span className="et-v2-state-label">{stateLabel}</span>
        </div>
      </div>

      <div className="et-v2-subtitle">{subtitle}</div>

      {isWait ? (
        <div className="et-v2-unlock">
          <div className="et-v2-unlock-label">Unlock when</div>
          <div className="et-v2-unlock-body">
            Spot tags support or resistance with trap below threshold
          </div>
        </div>
      ) : null}

      <div className="et-v2-grid">
        {cells.map((cell) => (
          <div
            key={cell.key}
            className={`et-v2-cell${cell.empty ? " et-v2-cell-empty" : ""}`}
          >
            <span className="et-v2-cell-label">{cell.label}</span>
            <span className="et-v2-cell-value">{cell.value}</span>
            {cell.subValue ? (
              <span className="et-v2-cell-sub">{cell.subValue}</span>
            ) : null}
          </div>
        ))}
      </div>

      {!isWait && (entryTarget.stop_brief || entryTarget.target_brief || entryTarget.rr_brief) ? (
        <div className="et-v2-notes">
          {entryTarget.stop_brief ? (
            <div className="et-v2-note">{entryTarget.stop_brief}</div>
          ) : null}
          {entryTarget.target_brief || entryTarget.rr_brief ? (
            <div className="et-v2-note">
              {entryTarget.target_brief || entryTarget.rr_brief}
            </div>
          ) : null}
        </div>
      ) : null}

      {magnetConflictWarning ? (
        <div className="et-v2-warning">{magnetConflictWarning}</div>
      ) : null}

      {entryTarget.compression_zone && entryTarget.price_magnet_strike && entryTarget.secondary_magnet ? (
        <div className="et-v2-compression">
          Compressed between {fmt(entryTarget.price_magnet_strike)} and{" "}
          {fmt(entryTarget.secondary_magnet)} · price pinned
        </div>
      ) : null}

      <div className="et-v2-context">
        <div className="et-v2-context-header">
          <span className="et-v2-context-label">Market Context</span>
          <span className="et-v2-context-tag">Ambient</span>
        </div>
        <div className="et-v2-context-grid">
          <div className="et-v2-context-item et-v2-context-magnet">
            <span className="et-v2-context-key">Magnet</span>
            <span className="et-v2-context-val">
              {entryTarget.price_magnet_strike != null
                ? fmt(entryTarget.price_magnet_strike)
                : "—"}
              {magnetSub !== "—" ? (
                <span className="et-v2-context-sub">{magnetSub}</span>
              ) : null}
            </span>
          </div>
          <div className="et-v2-context-item et-v2-context-cewall">
            <span className="et-v2-context-key">CE Wall</span>
            <span className="et-v2-context-val">{fmt(entryTarget.call_wall_used)}</span>
          </div>
          <div className="et-v2-context-item et-v2-context-pewall">
            <span className="et-v2-context-key">PE Wall</span>
            <span className="et-v2-context-val">{fmt(entryTarget.put_wall_used)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EntryTargetCard;
