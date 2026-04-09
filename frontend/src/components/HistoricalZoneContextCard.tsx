type ZoneSummary = {
  zone_low?: number | null;
  zone_high?: number | null;
  center?: number | null;
  role?: string | null;
  score?: number | null;
  touches?: number | null;
  dominant?: boolean | null;
  dominance_ratio?: number | null;
  first_date?: string | null;
  last_date?: string | null;
};

type HistoricalZoneContextCardProps = {
  available?: boolean;
  updatedAt?: string | null;
  fullWindow?: ZoneSummary | null;
  recentWindow?: ZoneSummary | null;
};

type Range100 = {
  low: number;
  high: number;
};

function formatNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function resolveZoneRange(zone?: ZoneSummary | null): Range100 | null {
  if (!zone) return null;
  const zoneLow =
    typeof zone.zone_low === "number" && Number.isFinite(zone.zone_low) ? zone.zone_low : null;
  const zoneHigh =
    typeof zone.zone_high === "number" && Number.isFinite(zone.zone_high) ? zone.zone_high : null;
  if (zoneLow === null || zoneHigh === null) return null;

  return {
    low: Math.min(zoneLow, zoneHigh),
    high: Math.max(zoneLow, zoneHigh),
  };
}

function formatRole(role?: string | null): string {
  const text = String(role || "").trim().toLowerCase();
  if (!text) return "-";
  if (text === "support") return "Support";
  if (text === "resistance") return "Resistance";
  if (text === "key_level" || text === "key level") return "Key Level";
  if (text === "acceptance") return "Acceptance";
  return role || "-";
}

function formatTimeLabel(value?: string | null): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "-";
  return dt.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ZoneBlock({ title, zone }: { title: string; zone?: ZoneSummary | null }) {
  const range = resolveZoneRange(zone);
  const hasZone = Boolean(range);

  return (
    <div className="ia-hzc-zone">
      <div className="ia-kpi-label">{title}</div>
      {hasZone ? (
        <>
          <div className="ia-kpi-value-sm">
            {formatNumber(range?.low)} - {formatNumber(range?.high)}
          </div>
          <div className="ia-hzc-meta">
            <span>{formatRole(zone?.role)}</span>
            <span>Score {Math.round(Number(zone?.score ?? 0))}</span>
            <span>Touches {Math.round(Number(zone?.touches ?? 0))}</span>
            <span>{zone?.dominant ? "Strong Zone" : "Contested Zone"}</span>
          </div>
        </>
      ) : (
        <div className="ia-kpi-label">No zone snapshot yet</div>
      )}
    </div>
  );
}

export default function HistoricalZoneContextCard({
  available = false,
  updatedAt = null,
  fullWindow = null,
  recentWindow = null,
}: HistoricalZoneContextCardProps) {
  return (
    <div className="ia-card ia-hzc-card">
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Historical Zone Context</h3>
        <span className="ia-status-chip">{available ? "Ready" : "Pending"}</span>
      </div>

      <div className="ia-hzc-grid">
        <ZoneBlock title="3 Month Dominant Zone" zone={fullWindow} />
        <ZoneBlock title="Recent Dominant Zone" zone={recentWindow} />
      </div>

      <div className="ia-hzc-footer">
        <span className="ia-kpi-label">Updated: {formatTimeLabel(updatedAt)}</span>
      </div>
    </div>
  );
}
