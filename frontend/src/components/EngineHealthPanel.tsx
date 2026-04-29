type EngineHealthDetailStats = {
  min: number;
  max: number;
  average: number;
  variance: number;
};

type EngineHealthResponse = {
  trap_distribution_status: "ok" | "warning" | "error" | "no_data";
  wick_variation_status: "ok" | "warning" | "error" | "no_data";
  hold_time_status: "ok" | "warning" | "error" | "no_data";
  oi_normalization_status: "ok" | "warning" | "error" | "no_data";
  volume_normalization_status: "ok" | "warning" | "error" | "no_data";
  clarity_status: "ok" | "warning" | "error" | "no_data";
  generated_at?: string;
  detail?: {
    message?: string;
    cycles_analyzed?: number;
    trap_probability?: EngineHealthDetailStats;
    rejection_wick_score?: EngineHealthDetailStats;
    time_above_level_ratio?: EngineHealthDetailStats;
    oi_shift_score?: EngineHealthDetailStats;
    volume_expansion_score?: EngineHealthDetailStats;
    clarity?: EngineHealthDetailStats;
  };
};

type Props = {
  data: EngineHealthResponse | null;
};

function statusClass(status?: string) {
  if (status === "ok") return "eh-pill eh-ok";
  if (status === "warning") return "eh-pill eh-warning";
  if (status === "no_data") return "eh-pill eh-warning";
  return "eh-pill eh-error";
}

export default function EngineHealthPanel({ data }: Props) {
  if (!data) {
    return <div className="ia-card">Engine health not available.</div>;
  }

  const rows: Array<{ label: string; value: string | undefined }> = [
    { label: "Trap Distribution", value: data.trap_distribution_status },
    { label: "Wick Variation", value: data.wick_variation_status },
    { label: "Hold-Time Ratio", value: data.hold_time_status },
    { label: "OI Normalization", value: data.oi_normalization_status },
    { label: "Volume Normalization", value: data.volume_normalization_status },
    { label: "Clarity", value: data.clarity_status },
  ];

  const stats = data.detail;

  return (
    <div className="ia-card">
      <h3 className="ia-card-title">Engine Health (Developer)</h3>
      <div className="eh-grid">
        {rows.map((row) => (
          <div key={row.label} className="eh-row">
            <span className="eh-label">{row.label}</span>
            <span className={statusClass(row.value)}>{(row.value ?? "error").replace("_", " ").toUpperCase()}</span>
          </div>
        ))}
      </div>
      {stats ? (
        <div className="eh-meta">
          <div className="eh-meta-title">
            Last {stats.cycles_analyzed ?? 0} cycles
            {data.generated_at ? ` | Updated: ${new Date(data.generated_at).toLocaleTimeString()}` : ""}
          </div>
          <div className="eh-stats-grid">
            <div>Trap avg: {stats.trap_probability?.average ?? 0}</div>
            <div>Wick avg: {stats.rejection_wick_score?.average ?? 0}</div>
            <div>Hold avg: {stats.time_above_level_ratio?.average ?? 0}</div>
            <div>OI avg: {stats.oi_shift_score?.average ?? 0}</div>
            <div>Vol avg: {stats.volume_expansion_score?.average ?? 0}</div>
            <div>Clarity avg: {stats.clarity?.average ?? 0}</div>
          </div>
          {stats.message ? <div className="eh-meta-title">{stats.message}</div> : null}
        </div>
      ) : null}
    </div>
  );
}

export type { EngineHealthResponse };
