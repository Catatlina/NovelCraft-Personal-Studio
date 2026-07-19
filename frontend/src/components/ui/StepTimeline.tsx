import React, { useState } from "react";
import { Check } from "lucide-react";

export type StepStatus = "done" | "active" | "waiting";

export interface TimelineStep {
  key: string;
  label: string;
  status: StepStatus;
  detail?: React.ReactNode;
}

export interface StepTimelineProps {
  steps: TimelineStep[];
}

/**
 * Vertical timeline of steps. Each step shows a status dot (check for `done`,
 * pulsing highlight for `active`, muted for `waiting`) and clicking the step
 * label toggles its detail panel.
 */
export function StepTimeline({ steps }: StepTimelineProps): React.ReactElement {
  const [openKey, setOpenKey] = useState<string | null>(
    () => steps.find((s) => s.status === "active")?.key ?? steps[0]?.key ?? null,
  );

  const toggle = (key: string): void => {
    setOpenKey((prev) => (prev === key ? null : key));
  };

  return (
    <div className="step-timeline">
      {steps.map((step) => {
        const isOpen = openKey === step.key;
        return (
          <div key={step.key} className={`step ${step.status}`}>
            <span className="step-dot" aria-hidden="true">
              {step.status === "done" ? <Check size={16} /> : null}
            </span>
            <div className="step-body">
              <button
                type="button"
                className="step-label"
                onClick={() => toggle(step.key)}
                aria-expanded={isOpen}
              >
                {step.label}
              </button>
              {isOpen && step.detail && <div className="step-detail">{step.detail}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default StepTimeline;
