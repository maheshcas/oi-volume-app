type TradeChecklistCardProps = {
  entryTrigger: string;
  volumeConfirmation: string;
  oiConfirmation: string;
  invalidationLevel: string;
  title?: string;
};

function ChecklistRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      style={{
        display: "grid",
        gap: 4,
        padding: "10px 12px",
        borderRadius: 12,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "#93a4b8",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 14,
          lineHeight: 1.4,
          fontWeight: 600,
          color: "#eef5ff",
        }}
      >
        {value || "-"}
      </div>
    </div>
  );
}

export default function TradeChecklistCard({
  entryTrigger,
  volumeConfirmation,
  oiConfirmation,
  invalidationLevel,
  title = "Trade Checklist",
}: TradeChecklistCardProps) {
  return (
    <section
      className="ia-card"
      style={{
        display: "grid",
        gap: 12,
        padding: 14,
        borderRadius: 14,
        background: "rgba(10, 18, 30, 0.82)",
        border: "1px solid rgba(255,255,255,0.10)",
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "#b9c4c7",
        }}
      >
        {title}
      </div>

      <ChecklistRow label="Entry Trigger" value={entryTrigger} />
      <ChecklistRow label="Volume Confirmation" value={volumeConfirmation} />
      <ChecklistRow label="OI Confirmation" value={oiConfirmation} />
      <ChecklistRow label="Invalidation Level" value={invalidationLevel} />
    </section>
  );
}
