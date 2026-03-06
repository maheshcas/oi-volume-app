type RetailSummaryStripProps = {
  bias: string;
  readiness: string;
  support: string;
  resistance: string;
  trapRiskLabel: string;
};

export default function RetailSummaryStrip({
  bias,
  readiness,
  support,
  resistance,
  trapRiskLabel,
}: RetailSummaryStripProps) {
  return (
    <div className="ia-retail-strip" role="status" aria-live="polite">
      <span>
        <strong>Bias:</strong> {bias}
      </span>
      <span className="ia-strip-sep">|</span>
      <span>
        <strong>Readiness:</strong> {readiness}
      </span>
      <span className="ia-strip-sep">|</span>
      <span>
        <strong>Support:</strong> {support}
      </span>
      <span className="ia-strip-sep">|</span>
      <span>
        <strong>Resistance:</strong> {resistance}
      </span>
      <span className="ia-strip-sep">|</span>
      <span>
        <strong>Trap:</strong> {trapRiskLabel}
      </span>
    </div>
  );
}
