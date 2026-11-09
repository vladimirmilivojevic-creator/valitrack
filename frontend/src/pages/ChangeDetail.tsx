import { useQuery } from "@tanstack/react-query";
import { FileText, Play } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { GateChecklist } from "../components/Gate";
import { History } from "../components/History";
import { SignatureList, SignatureModal } from "../components/Signing";
import { Banner, Chip, ErrorNote, Field, Id, Loading, Modal, PageHeader, Panel, RiskChip, StatusChip, Tabs } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtDateTime } from "../lib/format";
import { useMeta, useUsers } from "../lib/queries";
import { CHANGE_FLOW, CHANGE_TYPES, IMPACT_LEVELS } from "../lib/status";
import { useAct } from "../lib/toast";
import type { Application, Change, ChangeImpact, Gate, ReportDoc, Run, TestCase } from "../lib/types";

type Dialog =
  | { kind: "assess"; impact: ChangeImpact }
  | { kind: "departments" }
  | { kind: "tests" }
  | { kind: "approve" }
  | { kind: "reject" }
  | { kind: "release" }
  | { kind: "report"; doc: ReportDoc }
  | { kind: "cancel" }
  | null;

export default function ChangeDetail() {
  const { id } = useParams();
  const { user, can } = useAuth();
  const { name } = useUsers();
  const act = useAct();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [tab, setTab] = useState<"change" | "history">("change");

  const { data: change, error, isLoading } = useQuery({ queryKey: ["change", id], queryFn: () => api.get<Change>(`/changes/${id}`) });
  const application = useQuery({ queryKey: ["application", String(change?.application_id)], enabled: !!change, queryFn: () => api.get<Application>(`/applications/${change!.application_id}`) });
  const tests = useQuery({ queryKey: ["tests", change?.application_id], enabled: !!change, queryFn: () => api.get<TestCase[]>(`/applications/${change!.application_id}/test-cases`) });
  const gate = useQuery({ queryKey: ["gate", change?.target_version_id], enabled: !!change?.target_version_id, queryFn: () => api.get<Gate>(`/versions/${change!.target_version_id}/gate`) });
  const runs = useQuery({ queryKey: ["runs", "change", change?.id], enabled: !!change, queryFn: () => api.get<Run[]>(`/runs?change_id=${change!.id}`) });
  const reports = useQuery({ queryKey: ["report-docs", change?.target_version_id], enabled: !!change?.target_version_id, queryFn: () => api.get<ReportDoc[]>(`/versions/${change!.target_version_id}/reports`) });

  if (isLoading) return <Loading />;
  if (error || !change) return <ErrorNote error={error} />;

  const mine = change.requested_by === user?.id;
  const live = application.data?.live_version;
  const regression = (tests.data ?? []).filter((t) => change.test_case_ids?.includes(t.id));
  const latest = (testId: number) => runs.data?.find((r) => r.test_case_id === testId);
  const draftReports = (reports.data ?? []).filter((d) => d.status === "draft");
  const approved = change.signatures.map((s) => s.meaning);
  const myMeaning = user?.role === "system_owner" ? "Owner approved" : "Approved";
  const canSignApproval = change.status === "pending_approval" && can("change.approve") && !mine && !approved.includes(myMeaning) && change.required_signatures.includes(myMeaning);
  const stopped = change.status === "rejected" || change.status === "cancelled";
  const currentIndex = CHANGE_FLOW.indexOf(change.status as (typeof CHANGE_FLOW)[number]);

  async function startTest(test: TestCase) {
    const run = await act(() => api.post<Run>("/runs", { test_case_id: test.id, version_id: change!.target_version_id, change_request_id: change!.id }));
    navigate(`/runs/${run.id}`);
  }

  return (
    <>
      <PageHeader
        crumbs={[{ to: "/changes", label: "Change control" }]}
        eyebrow={change.code}
        title={change.title}
        subtitle={`${change.application_name}: ${live ? `v${live.version}` : "live version"} to v${change.target_version}. Requested by ${name(change.requested_by)} on ${fmtDate(change.created_at)}.`}
        actions={<><StatusChip status={change.status} /><RiskChip level={change.risk_level} /><Chip tone="neutral" outline>{CHANGE_TYPES[change.change_type]}</Chip></>}
      />

      <ol className="stepper" aria-label="Change workflow" style={{ marginBottom: 22, overflowX: "auto" }}>
        {CHANGE_FLOW.map((step, index) => (
          <li key={step} className={`${!stopped && index < currentIndex ? "done" : ""} ${!stopped && index === currentIndex ? "current" : ""} ${stopped && index === 0 ? "stopped" : ""}`}>
            <span className="dot" />
            {step.replace(/_/g, " ")}
          </li>
        ))}
        {stopped && <li className="stopped"><span className="dot" />{change.status}</li>}
      </ol>

      {stopped && change.decision_reason && <Banner tone="fail"><p><strong>{change.status === "rejected" ? "Rejected" : "Cancelled"}:</strong> {change.decision_reason}</p></Banner>}
      {change.requires_revalidation && change.status !== "released" && <Banner tone="warn"><p>A department said this change affects the validated state, so the affected functions must be retested before release.</p></Banner>}

      <Tabs tabs={[{ key: "change", label: "Change" }, { key: "history", label: "History" }]} value={tab} onChange={setTab} />
      {tab === "history" ? (
        <Panel flush title="History of this change"><History entityType="change_request" entityId={change.id} /></Panel>
      ) : (
        <div className="grid-2">
          <div className="stack-lg">
            <Panel title="Next step">
              <div className="stack">
                {change.status === "draft" && (mine || can("change.coordinate")) && <button className="btn btn--primary" onClick={() => void act(() => api.post(`/changes/${change.id}/submit`), "Change submitted.")}>Submit the change request</button>}
                {change.status === "submitted" && can("change.coordinate") && <button className="btn btn--primary" onClick={() => setDialog({ kind: "departments" })}>Start the impact assessment</button>}
                {change.status === "submitted" && !can("change.coordinate") && <p className="muted">Waiting for QA to start the impact assessment.</p>}
                {change.status === "impact_assessment" && <p>Each department gives its impact. When all have answered, the risk is worked out and the change goes to approval.</p>}
                {change.status === "pending_approval" && (
                  <>
                    <p>Needs: {change.required_signatures.map((m) => `${m}${approved.includes(m) ? " (signed)" : ""}`).join(" and ")}.</p>
                    {canSignApproval && <div className="row"><button className="btn btn--primary" onClick={() => setDialog({ kind: "approve" })}>Approve ({myMeaning})</button>{user?.role === "qa_manager" && <button className="btn btn--danger" onClick={() => setDialog({ kind: "reject" })}>Reject</button>}</div>}
                    {mine && <p className="small muted">You requested this change, so you cannot approve it.</p>}
                  </>
                )}
                {change.status === "approved" && can("change.coordinate") && <button className="btn btn--primary" onClick={() => setDialog({ kind: "tests" })}>Plan the tests and start testing</button>}
                {change.status === "approved" && !can("change.coordinate") && <p className="muted">Approved. QA plans the tests next.</p>}
                {change.status === "testing" && (
                  <>
                    <p>Execute the regression tests on version {change.target_version}, get them reviewed and close deviations.</p>
                    {can("change.coordinate") && <button className="btn btn--primary" onClick={() => void act(() => api.post(`/changes/${change.id}/complete-testing`), "Testing completed.")}>Complete testing</button>}
                  </>
                )}
                {change.status === "ready_for_release" && (
                  <>
                    <p>Generate the validation report, let QA approve it, then release.</p>
                    {can("report.generate") && <button className="btn" onClick={() => void act(() => api.post(`/versions/${change.target_version_id}/reports`), "Report generated.")}><FileText size={15} aria-hidden="true" /> Generate validation report</button>}
                    {draftReports.map((doc) => (
                      <div key={doc.id} className="row">
                        <a className="id" href={`/api/report-documents/${doc.id}/pdf`} target="_blank" rel="noreferrer">{doc.doc_number}</a>
                        <span className="muted small">{fmtDateTime(doc.generated_at)}</span>
                        {can("report.approve") && doc.generated_by !== user?.id && <button className="btn btn--sm" onClick={() => setDialog({ kind: "report", doc })}>Approve report</button>}
                      </div>
                    ))}
                    {can("change.release") && !mine && gate.data?.passed && <button className="btn btn--primary" onClick={() => setDialog({ kind: "release" })}>Release version {change.target_version}</button>}
                  </>
                )}
                {change.status === "released" && <p>Released {fmtDateTime(change.released_at)}. Everybody who was trained on the older version must be trained again; see <Link to="/training">Training</Link>.</p>}
                {["draft", "submitted", "impact_assessment", "pending_approval", "approved"].includes(change.status) && (mine || can("change.coordinate")) && (
                  <button className="btn btn--ghost" onClick={() => setDialog({ kind: "cancel" })}>Cancel this change</button>
                )}
              </div>
            </Panel>

            <Panel title="The request">
              <dl className="kv">
                <dt>Business need</dt><dd>{change.business_need}</dd>
                <dt>What changes</dt><dd>{change.description}</dd>
                <dt>Priority</dt><dd><StatusChip status={change.priority} /></dd>
                <dt>Planned release</dt><dd>{fmtDate(change.planned_release_date)}</dd>
                <dt>Requirements</dt><dd>{change.affects_requirements ? "change; they need a new approval" : "unchanged; the approved baseline is inherited"}</dd>
              </dl>
            </Panel>

            <Panel title="Impact assessment by department" flush>
              {change.impacts.length === 0 ? <p className="muted" style={{ padding: 16, margin: 0 }}>The coordinator chooses the departments when the assessment starts.</p> : (
                <table className="table">
                  <thead><tr><th>Department</th><th>Impact</th><th>Affects validated state</th><th>Comment</th><th /></tr></thead>
                  <tbody>
                    {change.impacts.map((i) => (
                      <tr key={i.id}>
                        <td><strong>{i.department}</strong></td>
                        <td>{i.impact_level ? <StatusChip status={i.impact_level} /> : <Chip tone="warn">Waiting</Chip>}</td>
                        <td>{i.affects_validated_state === null ? "-" : i.affects_validated_state ? "Yes" : "No"}</td>
                        <td className="small">{i.comment}{i.assessor_id && <div className="sub">{name(i.assessor_id)}, {fmtDateTime(i.assessed_at)}</div>}</td>
                        <td>{change.status === "impact_assessment" && can("change.assess") && <button className="btn btn--sm" onClick={() => setDialog({ kind: "assess", impact: i })}>{i.assessed_at ? "Update" : "Assess"}</button>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          </div>

          <div className="stack-lg">
            <Panel title="Signatures"><SignatureList signatures={change.signatures} empty="No signatures yet." /></Panel>
            {change.target_version_id && (
              <>
                <Panel title={`Regression tests on v${change.target_version}`} flush>
                  {regression.length === 0 ? <p className="muted" style={{ padding: 16, margin: 0 }}>The tests are chosen when testing starts.</p> : (
                    <table className="table">
                      <tbody>
                        {regression.map((t) => {
                          const run = latest(t.id);
                          return (
                            <tr key={t.id}>
                              <td><Id>{t.code}</Id> {t.title}</td>
                              <td>{run ? <Link to={`/runs/${run.id}`}><StatusChip status={run.status === "completed" ? run.result : "in_progress"} /></Link> : <span className="muted small">not run</span>}</td>
                              <td>{change.status === "testing" && can("run.execute") && (!run || run.result !== "passed") && <button className="btn btn--sm" onClick={() => void startTest(t)}><Play size={13} aria-hidden="true" /> {run ? "Run again" : "Execute"}</button>}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </Panel>
                {gate.data && <Panel title="Release gate">{<GateChecklist gate={gate.data} />}</Panel>}
              </>
            )}
          </div>
        </div>
      )}

      {dialog?.kind === "departments" && <DepartmentsDialog onClose={() => setDialog(null)} onStart={(departments) => act(() => api.post(`/changes/${change.id}/start-assessment`, { departments }), "Impact assessment started.")} />}
      {dialog?.kind === "assess" && <AssessDialog impact={dialog.impact} onClose={() => setDialog(null)} onSave={(body) => act(() => api.put(`/changes/${change.id}/impacts/${encodeURIComponent(dialog.impact.department)}`, body), "Assessment saved.")} />}
      {dialog?.kind === "tests" && <TestsDialog tests={(tests.data ?? []).filter((t) => t.status === "approved")} onClose={() => setDialog(null)} onStart={(ids) => act(() => api.post(`/changes/${change.id}/start-testing`, { test_case_ids: ids }), "Testing started.")} />}
      {dialog?.kind === "approve" && (
        <SignatureModal title="Approve the change" meaning={myMeaning} record={`${change.code}: ${change.title}`}
          summary={<p className="small">Risk level: <strong>{change.risk_level}</strong>. By signing you confirm that the impact assessments are complete and the change may go to testing.</p>}
          onSign={(password, comment) => act(() => api.post(`/changes/${change.id}/approve`, { password, comment }), "Signature recorded.")} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "reject" && (
        <SignatureModal title="Reject the change" meaning="Reviewed" record={`${change.code}: ${change.title}`} commentLabel="Reason for the rejection" commentRequired confirmLabel="Reject and sign"
          onSign={(password, reason) => act(() => api.post(`/changes/${change.id}/reject`, { password, reason }), "Change rejected.")} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "report" && (
        <SignatureModal title="Approve the validation report" meaning="Approved" record={dialog.doc.doc_number}
          onSign={(password, comment) => act(() => api.post(`/report-documents/${dialog.doc.id}/approve`, { password, comment }), "Report approved.")} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "release" && (
        <SignatureModal title={`Release version ${change.target_version}`} meaning="Released" record={`${change.application_name} ${change.target_version} becomes the validated version`}
          summary={<p className="small">The old version is superseded. People trained on it will need training on the new one.</p>}
          onSign={(password, comment) => act(() => api.post(`/changes/${change.id}/release`, { password, comment }), "Version released.")} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "cancel" && <CancelDialog onClose={() => setDialog(null)} onCancel={(reason) => act(() => api.post(`/changes/${change.id}/cancel`, { reason }), "Change cancelled.")} />}
    </>
  );
}

function DepartmentsDialog({ onClose, onStart }: { onClose: () => void; onStart: (departments: string[]) => Promise<unknown> }) {
  const { data: meta } = useMeta();
  const [chosen, setChosen] = useState<string[]>(["IT"]);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await onStart(chosen); onClose(); } catch (e) { setError(errorMessage(e)); }
  }
  return (
    <Modal title="Start the impact assessment" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="dept-form">Start</button></>}>
      <form id="dept-form" onSubmit={submit}>
        <p>Which departments must say how this change affects them? Quality Assurance is always asked.</p>
        {meta?.departments.filter((d) => d !== "Quality Assurance").map((d) => (
          <label key={d} className="check"><input type="checkbox" checked={chosen.includes(d)} onChange={(e) => setChosen(e.target.checked ? [...chosen, d] : chosen.filter((x) => x !== d))} /> {d}</label>
        ))}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function AssessDialog({ impact, onClose, onSave }: { impact: ChangeImpact; onClose: () => void; onSave: (body: { impact_level: string; affects_validated_state: boolean; comment: string }) => Promise<unknown> }) {
  const [level, setLevel] = useState<string>(impact.impact_level ?? "low");
  const [affects, setAffects] = useState(impact.affects_validated_state ?? false);
  const [comment, setComment] = useState(impact.comment ?? "");
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await onSave({ impact_level: level, affects_validated_state: affects, comment }); onClose(); } catch (e) { setError(errorMessage(e)); }
  }
  return (
    <Modal title={`Impact on ${impact.department}`} onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="assess-form">Save assessment</button></>}>
      <form id="assess-form" onSubmit={submit}>
        <Field label="How strongly does the change affect this department?" htmlFor="i-level">
          <select id="i-level" className="select" value={level} onChange={(e) => setLevel(e.target.value)}>{IMPACT_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}</select>
        </Field>
        <label className="check"><input type="checkbox" checked={affects} onChange={(e) => setAffects(e.target.checked)} /> It affects the validated state, so functions must be retested</label>
        <Field label="Comment" hint="Say what you looked at and why you came to this answer." htmlFor="i-comment"><textarea id="i-comment" className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} required /></Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function TestsDialog({ tests, onClose, onStart }: { tests: TestCase[]; onClose: () => void; onStart: (ids: number[]) => Promise<unknown> }) {
  const [chosen, setChosen] = useState<number[]>(tests.map((t) => t.id));
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await onStart(chosen); onClose(); } catch (e) { setError(errorMessage(e)); }
  }
  return (
    <Modal title="Plan the regression tests" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="plan-form" disabled={chosen.length === 0}>Start testing</button></>}>
      <form id="plan-form" onSubmit={submit}>
        <p>Choose the tests that prove the validated state still holds. Tests that cover high-risk requirements should always be included.</p>
        {tests.map((t) => (
          <label key={t.id} className="check"><input type="checkbox" checked={chosen.includes(t.id)} onChange={(e) => setChosen(e.target.checked ? [...chosen, t.id] : chosen.filter((x) => x !== t.id))} /><span><Id>{t.code}</Id> {t.title} <span className="muted small">({t.test_type})</span></span></label>
        ))}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function CancelDialog({ onClose, onCancel }: { onClose: () => void; onCancel: (reason: string) => Promise<unknown> }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await onCancel(reason); onClose(); } catch (e) { setError(errorMessage(e)); }
  }
  return (
    <Modal title="Cancel the change" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Keep it</button><button className="btn btn--danger" type="submit" form="cancel-form">Cancel the change</button></>}>
      <form id="cancel-form" onSubmit={submit}>
        <Field label="Reason" htmlFor="x-reason"><input id="x-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus /></Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
