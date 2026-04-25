import type { ReactNode } from "react";

type AdvancedAnalysisCardProps = {
  open: boolean;
  onToggle: () => void;
  preview: ReactNode;
  children: ReactNode;
};

export default function AdvancedAnalysisCard({
  open,
  onToggle,
  preview,
  children,
}: AdvancedAnalysisCardProps) {
  return (
    <div className={`ia-card ia-collapsible ${open ? "" : "ia-collapsed"}`}>
      <div className="ia-card-title-row">
        <h3 className="ia-card-title">Advanced Analysis</h3>
        <button type="button" className="ia-detail-toggle" onClick={onToggle}>
          {open ? "Hide Details" : "Show Details"}
        </button>
      </div>
      {!open ? <div className="ia-preview-line">{preview}</div> : <div className="ia-advanced-stack">{children}</div>}
    </div>
  );
}
