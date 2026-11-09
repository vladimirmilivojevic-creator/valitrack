import { CheckCircle2, XCircle } from "lucide-react";
import type { BoardRow, Gate } from "../lib/types";

/** The release gate as a checklist. Every line says in words why it is open or met. */
export function GateChecklist({ gate }: { gate: Gate }) {
  const met = gate.checks.filter((c) => c.passed).length;
  return (
    <div>
      <p className="small muted" style={{ marginBottom: 6 }}>
        {met} of {gate.checks.length} checks met
        {gate.passed ? ". The version can be released." : gate.ready_for_report ? ". Only the report approval is open." : "."}
      </p>
      <ul className="gate">
        {gate.checks.map((check) => (
          <li key={check.key} className={check.passed ? "ok" : "open"}>
            {check.passed ? <CheckCircle2 size={18} aria-label="Met" /> : <XCircle size={18} aria-label="Open" />}
            <div>
              <strong>{check.label}</strong>
              <span className="detail">{check.detail}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

const STAGES: { key: BoardRow["stage"]; label: string }[] = [
  { key: "requirements", label: "Requirements" },
  { key: "testing", label: "Testing" },
  { key: "report", label: "Report" },
  { key: "release", label: "Release" },
  { key: "validated", label: "Validated" },
];

/** Where a version is in its validation: requirements, testing, report, release. */
export function LifecycleStepper({ stage }: { stage: BoardRow["stage"] }) {
  const current = STAGES.findIndex((s) => s.key === stage);
  return (
    <ol className="stepper" aria-label={`Lifecycle stage: ${STAGES[current]?.label}`}>
      {STAGES.map((s, index) => {
        const done = stage === "validated" ? true : index < current;
        const isCurrent = stage !== "validated" && index === current;
        return (
          <li key={s.key} className={`${done ? "done" : ""} ${isCurrent ? "current" : ""}`} aria-current={isCurrent ? "step" : undefined}>
            <span className="dot" />
            {s.label}
          </li>
        );
      })}
    </ol>
  );
}
