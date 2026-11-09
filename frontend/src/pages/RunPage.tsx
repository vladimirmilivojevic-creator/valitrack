import { useQuery } from "@tanstack/react-query";
import { Paperclip } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { SignatureList, SignatureModal } from "../components/Signing";
import { Banner, Chip, ErrorNote, Loading, PageHeader, Panel, StatusChip } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fileSize, fmtDateTime, shortHash } from "../lib/format";
import { useUsers } from "../lib/queries";
import { useAct } from "../lib/toast";
import type { Deviation, Run, RunStep } from "../lib/types";

const RESULTS: { key: RunStep["result"]; label: string; tone: string }[] = [
  { key: "passed", label: "Passed", tone: "pass" },
  { key: "failed", label: "Failed", tone: "fail" },
  { key: "blocked", label: "Blocked", tone: "warn" },
  { key: "na", label: "N/A", tone: "neutral" },
];

export default function RunPage() {
  const { id } = useParams();
  const { user, can } = useAuth();
  const { name } = useUsers();
  const act = useAct();
  const [signing, setSigning] = useState<"complete" | "review" | null>(null);
  const { data: run, error, isLoading } = useQuery({ queryKey: ["run", id], queryFn: () => api.get<Run>(`/runs/${id}`) });
  const deviations = useQuery({
    queryKey: ["deviations", "app", run?.application_id],
    enabled: run?.result === "failed",
    queryFn: () => api.get<Deviation[]>(`/deviations?application_id=${run!.application_id}`),
  });

  if (isLoading) return <Loading />;
  if (error || !run) return <ErrorNote error={error} />;

  const editable = run.status === "in_progress" && run.executed_by === user?.id && can("run.execute");
  const open = run.steps.filter((s) => s.result === "pending").length;
  const deviation = deviations.data?.find((d) => d.test_run_id === run.id);
  const canReview = run.status === "completed" && !run.reviewed_at && can("run.review") && run.executed_by !== user?.id;

  return (
    <>
      <PageHeader
        crumbs={[{ to: "/applications", label: "Applications" }, { to: `/applications/${run.application_id}?tab=runs`, label: "Executions" }]}
        eyebrow={`RUN-${run.id} · ${run.test_type} test`}
        title={`${run.test_code} ${run.test_title}`}
        subtitle={`Executed on version ${run.version} by ${name(run.executed_by)}. Test case revision ${run.test_case_revision}.`}
        actions={
          <>
            <StatusChip status={run.status === "completed" ? run.result : "in_progress"} />
            {run.reviewed_at && <Chip tone="pass">Reviewed by {name(run.reviewed_by)}</Chip>}
          </>
        }
      />

      {editable && (
        <Banner tone="info">
          <p>Record the result of every step. Failed and blocked steps need a description of what you saw. Add evidence where it helps, then complete the run with your signature.</p>
        </Banner>
      )}
      {run.status === "in_progress" && !editable && (
        <Banner tone="warn"><p>This run is in progress. Only {name(run.executed_by)} can record results.</p></Banner>
      )}
      {deviation && (
        <Banner tone="fail">
          <p>This failure opened deviation <Link to="/deviations">{deviation.code}</Link> ({deviation.status.replace("_", " ")}). QA must analyse and close it before the version can be released.</p>
        </Banner>
      )}

      <div className="grid-2">
        <div>
          {run.steps.map((step) => (
            <StepCard key={`${step.step_no}-${step.result}-${step.evidence.length}`} run={run} step={step} editable={editable} />
          ))}
        </div>
        <div className="stack-lg">
          <Panel title="Run">
            <dl className="kv">
              <dt>Started</dt><dd>{fmtDateTime(run.started_at)}</dd>
              <dt>Completed</dt><dd>{fmtDateTime(run.completed_at)}</dd>
              <dt>Steps open</dt><dd>{open}</dd>
            </dl>
            <div className="stack" style={{ marginTop: 14 }}>
              {editable && (
                <button className="btn btn--primary" disabled={open > 0} onClick={() => setSigning("complete")}>
                  Complete the run and sign
                </button>
              )}
              {editable && open > 0 && <span className="small muted">{open} steps still need a result.</span>}
              {canReview && <button className="btn btn--primary" onClick={() => setSigning("review")}>Review and sign</button>}
            </div>
            {run.review_comment && <p className="small" style={{ marginTop: 12 }}>QA review: “{run.review_comment}”</p>}
          </Panel>
          <Panel title="Signatures">
            <SignatureList signatures={run.signatures} empty="Nobody has signed this run yet." />
          </Panel>
        </div>
      </div>

      {signing === "complete" && (
        <SignatureModal
          title="Complete the test run"
          meaning="Executed"
          record={`${run.test_code} run ${run.id} on version ${run.version}`}
          summary={<p className="small">The signature covers every step result and the hash of every evidence file. After signing, nothing in this run can be changed.</p>}
          onSign={(password, comment) => act(() => api.post(`/runs/${run.id}/complete`, { password, comment }), "Run completed.")}
          onClose={() => setSigning(null)}
        />
      )}
      {signing === "review" && (
        <SignatureModal
          title="Review the test run"
          meaning="Reviewed"
          record={`${run.test_code} run ${run.id}: result ${run.result}`}
          summary={<p className="small">QA confirms that the steps were done as written, the results are documented and the evidence supports the result.</p>}
          commentLabel="Review comment"
          onSign={(password, comment) => act(() => api.post(`/runs/${run.id}/review`, { password, comment }), "Run reviewed.")}
          onClose={() => setSigning(null)}
        />
      )}
    </>
  );
}

function StepCard({ run, step, editable }: { run: Run; step: RunStep; editable: boolean }) {
  const act = useAct();
  const [result, setResult] = useState<RunStep["result"]>(step.result);
  const [actual, setActual] = useState(step.actual_result ?? "");
  const [comment, setComment] = useState(step.comment ?? "");
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const dirty = result !== step.result || actual !== (step.actual_result ?? "") || comment !== (step.comment ?? "");

  async function save() {
    setBusy(true);
    try {
      await act(() => api.put(`/runs/${run.id}/steps/${step.step_no}`, { result, actual_result: actual || null, comment: comment || null }));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setBusy(true);
    try {
      await act(() => api.upload(`/runs/${run.id}/steps/${step.step_no}/evidence`, file), "Evidence added.");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <div className={`step-card ${step.result !== "pending" ? step.result : ""}`}>
      <div className="step-card__head">
        <span className="step-card__no">{step.step_no}</span>
        <div>
          <strong>{step.action}</strong>
          <div className="expected"><b>Expected result</b>{step.expected_result}</div>
        </div>
        <StatusChip status={step.result} />
      </div>
      <div className="step-card__body">
        {editable ? (
          <>
            <div className="field">
              <span className="label">Result</span>
              <div className="seg" role="group" aria-label={`Result of step ${step.step_no}`}>
                {RESULTS.map((r) => (
                  <button key={r.key} type="button" data-tone={r.tone} aria-pressed={result === r.key} onClick={() => setResult(r.key)}>{r.label}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <label htmlFor={`actual-${step.step_no}`}>What did you see?</label>
              <textarea id={`actual-${step.step_no}`} className="textarea" style={{ minHeight: 60 }} value={actual} onChange={(e) => setActual(e.target.value)} />
            </div>
            <div className="row">
              <button className="btn btn--sm" disabled={busy || result === "pending" || !dirty} onClick={() => void save()}>Save result</button>
              <input ref={fileInput} type="file" accept="image/png,image/jpeg,application/pdf,text/plain" hidden onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
              <button className="btn btn--sm btn--ghost" disabled={busy} onClick={() => fileInput.current?.click()}><Paperclip size={14} aria-hidden="true" /> Add evidence</button>
              <span className="small muted">PNG, JPEG, PDF or text, up to 2 MB</span>
            </div>
          </>
        ) : (
          step.actual_result && <p style={{ marginBottom: 8 }}><strong>Seen:</strong> {step.actual_result}</p>
        )}
        {step.evidence.length > 0 && (
          <ul style={{ margin: "10px 0 0", padding: 0, listStyle: "none" }}>
            {step.evidence.map((e) => (
              <li key={e.id} className="small">
                <Paperclip size={13} aria-hidden="true" />{" "}
                <a href={`/api/evidence/${e.id}`} target="_blank" rel="noreferrer">{e.filename}</a>{" "}
                <span className="muted">({fileSize(e.size_bytes)}, SHA-256 <span className="mono">{shortHash(e.sha256, 12)}</span>)</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
