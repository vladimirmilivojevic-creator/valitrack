import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Pencil, Play, Plus } from "lucide-react";
import { Fragment, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SignatureList, SignatureModal } from "../../components/Signing";
import { Chip, Empty, Field, Id, Loading, Modal, Panel, StatusChip, Term } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useAct } from "../../lib/toast";
import type { Application, Requirement, Run, Signature, TestCase } from "../../lib/types";

export default function Tests({ app }: { app: Application }) {
  const { can } = useAuth();
  const act = useAct();
  const navigate = useNavigate();
  const [open, setOpen] = useState<number | null>(null);
  const [editing, setEditing] = useState<TestCase | "new" | null>(null);
  const [approving, setApproving] = useState<TestCase | null>(null);
  const [retiring, setRetiring] = useState<TestCase | null>(null);

  const tests = useQuery({ queryKey: ["tests", app.id], queryFn: () => api.get<TestCase[]>(`/applications/${app.id}/test-cases`) });
  const reqs = useQuery({ queryKey: ["requirements", app.id], queryFn: () => api.get<Requirement[]>(`/applications/${app.id}/requirements`) });
  const version = app.working_version;
  const runs = useQuery({
    queryKey: ["runs", "version", version?.id],
    enabled: !!version,
    queryFn: () => api.get<Run[]>(`/runs?version_id=${version!.id}`),
  });

  const latest = (testId: number) => runs.data?.find((r) => r.test_case_id === testId);
  const codeOf = (id: number) => reqs.data?.find((r) => r.id === id)?.code ?? `#${id}`;

  async function start(test: TestCase) {
    if (!version) return;
    const run = await act(() => api.post<Run>("/runs", { test_case_id: test.id, version_id: version.id }));
    navigate(`/runs/${run.id}`);
  }

  if (tests.isLoading) return <Loading />;
  const items = tests.data ?? [];

  return (
    <div className="stack-lg">
      <Panel
        title={`Test cases (${items.length})`}
        flush
        actions={
          can("test.write") && (
            <button className="btn btn--sm" onClick={() => setEditing("new")}>
              <Plus size={14} aria-hidden="true" /> New test case
            </button>
          )
        }
      >
        {items.length === 0 ? (
          <Empty title="No test cases yet">Write <Term k="IQ">IQ</Term>, <Term k="OQ">OQ</Term> and <Term k="PQ">PQ</Term> tests and link each one to the requirements it proves.</Empty>
        ) : (
          <div className="scroll-x">
            <table className="table">
              <thead>
                <tr><th /><th>Test</th><th>Type</th><th>Status</th><th>Covers</th><th>Latest run{version ? ` on ${version.version}` : ""}</th><th /></tr>
              </thead>
              <tbody>
                {items.map((t) => {
                  const run = latest(t.id);
                  const isOpen = open === t.id;
                  return (
                    <Fragment key={t.id}>
                      <tr style={t.status === "retired" ? { opacity: 0.55 } : undefined}>
                        <td style={{ width: 34 }}>
                          <button className="btn btn--ghost btn--icon btn--sm" onClick={() => setOpen(isOpen ? null : t.id)} aria-expanded={isOpen} aria-label={`Show steps of ${t.code}`}>
                            {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          </button>
                        </td>
                        <td>
                          <div className="title"><Id>{t.code}</Id> {t.title}</div>
                          <div className="sub">revision {t.revision} · {t.style}</div>
                        </td>
                        <td><Chip tone="neutral" outline>{t.test_type}</Chip></td>
                        <td><StatusChip status={t.status} /></td>
                        <td>{t.requirement_ids.map((id) => <Id key={id}>{codeOf(id)} </Id>)}</td>
                        <td>{run ? <Link to={`/runs/${run.id}`}><StatusChip status={run.status === "completed" ? run.result : "in_progress"} /></Link> : <span className="muted">not run</span>}</td>
                        <td className="nowrap">
                          {t.status === "approved" && version && can("run.execute") && (
                            <button className="btn btn--sm" onClick={() => void start(t)}><Play size={13} aria-hidden="true" /> Execute</button>
                          )}
                          {t.status === "draft" && can("test.approve") && (
                            <button className="btn btn--sm" onClick={() => setApproving(t)}>Approve</button>
                          )}
                          {can("test.write") && t.status !== "retired" && (
                            <>
                              <button className="btn btn--sm btn--ghost" onClick={() => setEditing(t)} aria-label={`Edit ${t.code}`}><Pencil size={14} /></button>
                              <button className="btn btn--sm btn--ghost" onClick={() => setRetiring(t)}>Retire</button>
                            </>
                          )}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td />
                          <td colSpan={6}>
                            <TestDetails test={t} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {editing && <TestDialog app={app} test={editing === "new" ? null : editing} requirements={reqs.data ?? []} onClose={() => setEditing(null)} />}
      {approving && (
        <SignatureModal
          title={`Approve ${approving.code}`}
          meaning="Approved"
          record={`${approving.code} revision ${approving.revision}: ${approving.title}`}
          summary={<p className="small">QA confirms that the steps and expected results prove the linked requirements. The author of a test cannot approve it.</p>}
          onSign={(password, comment) => act(() => api.post(`/test-cases/${approving.id}/approve`, { password, comment }), "Test case approved.")}
          onClose={() => setApproving(null)}
        />
      )}
      {retiring && <RetireDialog test={retiring} onClose={() => setRetiring(null)} />}
    </div>
  );
}

function TestDetails({ test }: { test: TestCase }) {
  const { data } = useQuery({
    queryKey: ["signatures", "test_case", test.id],
    queryFn: () => api.get<Signature[]>(`/signatures?entity_type=test_case&entity_id=${test.id}`),
  });
  return (
    <div style={{ padding: "4px 0 10px" }}>
      <p><strong>Objective.</strong> {test.objective}</p>
      {test.preconditions && <p><strong>Preconditions.</strong> {test.preconditions}</p>}
      {test.steps.length > 0 ? (
        <table className="table">
          <thead><tr><th>Step</th><th>Action</th><th>Expected result</th></tr></thead>
          <tbody>
            {test.steps.map((s) => (
              <tr key={s.step_no}><td className="id">{s.step_no}</td><td>{s.action}</td><td>{s.expected_result}</td></tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted small">Unscripted test: the tester explores and records what was done and seen. Allowed for low-risk requirements only.</p>
      )}
      <div style={{ marginTop: 12 }}><SignatureList signatures={(data ?? []).filter((s) => s.entity_label.includes(`revision ${test.revision}`))} empty="Not approved yet." /></div>
    </div>
  );
}

function TestDialog({ app, test, requirements, onClose }: { app: Application; test: TestCase | null; requirements: Requirement[]; onClose: () => void }) {
  const act = useAct();
  const [form, setForm] = useState({
    test_type: test?.test_type ?? "OQ",
    title: test?.title ?? "",
    objective: test?.objective ?? "",
    preconditions: test?.preconditions ?? "",
    style: test?.style ?? "scripted",
    steps: test?.steps.map((s) => ({ action: s.action, expected_result: s.expected_result })) ?? [{ action: "", expected_result: "" }],
    requirement_ids: test?.requirement_ids ?? ([] as number[]),
    reason: "",
  });
  const [error, setError] = useState<string | null>(null);
  const setStep = (index: number, key: "action" | "expected_result", value: string) =>
    setForm({ ...form, steps: form.steps.map((s, i) => (i === index ? { ...s, [key]: value } : s)) });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const steps = form.style === "unscripted" ? [] : form.steps.filter((s) => s.action.trim() || s.expected_result.trim());
    try {
      if (test) {
        await act(async () => {
          await api.patch(`/test-cases/${test.id}`, { title: form.title, objective: form.objective, preconditions: form.preconditions || null, style: form.style, steps, reason: form.reason });
          return api.put(`/test-cases/${test.id}/requirements`, { requirement_ids: form.requirement_ids });
        }, "Test case saved. It needs a new approval.");
      } else {
        await act(() => api.post(`/applications/${app.id}/test-cases`, { ...form, preconditions: form.preconditions || null, steps, reason: undefined }), "Test case created.");
      }
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title={test ? `Edit ${test.code}` : "New test case"} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="test-form">Save</button></>}>
      <form id="test-form" onSubmit={submit}>
        <div className="fields-3">
          <Field label="Type" htmlFor="t-type">
            <select id="t-type" className="select" value={form.test_type} onChange={(e) => setForm({ ...form, test_type: e.target.value as "IQ" | "OQ" | "PQ" })} disabled={!!test}>
              <option value="IQ">IQ installation</option><option value="OQ">OQ functions</option><option value="PQ">PQ real process</option>
            </select>
          </Field>
          <Field label="Style" hint="Unscripted is for low-risk requirements." htmlFor="t-style">
            <select id="t-style" className="select" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value as "scripted" | "unscripted" })}>
              <option value="scripted">Scripted (steps)</option><option value="unscripted">Unscripted (exploratory)</option>
            </select>
          </Field>
        </div>
        <Field label="Title" htmlFor="t-title"><input id="t-title" className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required autoFocus /></Field>
        <Field label="Objective" hint="What does this test prove?" htmlFor="t-obj"><textarea id="t-obj" className="textarea" value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} required /></Field>
        <Field label="Preconditions (optional)" htmlFor="t-pre"><input id="t-pre" className="input" value={form.preconditions} onChange={(e) => setForm({ ...form, preconditions: e.target.value })} /></Field>

        {form.style === "scripted" && (
          <div className="field">
            <span className="label">Steps</span>
            {form.steps.map((step, index) => (
              <div key={index} className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap", marginBottom: 6 }}>
                <span className="id" style={{ paddingTop: 9 }}>{index + 1}</span>
                <input className="input" placeholder="Action" aria-label={`Action of step ${index + 1}`} value={step.action} onChange={(e) => setStep(index, "action", e.target.value)} />
                <input className="input" placeholder="Expected result" aria-label={`Expected result of step ${index + 1}`} value={step.expected_result} onChange={(e) => setStep(index, "expected_result", e.target.value)} />
                <button type="button" className="btn btn--ghost btn--sm" onClick={() => setForm({ ...form, steps: form.steps.filter((_, i) => i !== index) })} aria-label={`Remove step ${index + 1}`}>Remove</button>
              </div>
            ))}
            <div><button type="button" className="btn btn--sm" onClick={() => setForm({ ...form, steps: [...form.steps, { action: "", expected_result: "" }] })}>Add step</button></div>
          </div>
        )}

        <div className="field">
          <span className="label">Covers these requirements</span>
          {requirements.length === 0 && <span className="muted small">Write requirements first.</span>}
          {requirements.map((r) => (
            <label key={r.id} className="check">
              <input type="checkbox" checked={form.requirement_ids.includes(r.id)} onChange={(e) => setForm({ ...form, requirement_ids: e.target.checked ? [...form.requirement_ids, r.id] : form.requirement_ids.filter((id) => id !== r.id) })} />
              <span><Id>{r.code}</Id> {r.title}</span>
            </label>
          ))}
        </div>
        {test && (
          <Field label="Reason for the change" hint={test.status === "approved" ? "The test case goes back to draft and needs a new approval." : "Goes into the audit trail."} htmlFor="t-reason">
            <input id="t-reason" className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required />
          </Field>
        )}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function RetireDialog({ test, onClose }: { test: TestCase; onClose: () => void }) {
  const act = useAct();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await act(() => api.post(`/test-cases/${test.id}/retire`, { reason }), "Test case retired.");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  return (
    <Modal title={`Retire ${test.code}`} onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--danger" type="submit" form="retire-test">Retire</button></>}>
      <form id="retire-test" onSubmit={submit}>
        <Field label="Reason" htmlFor="rt-reason"><input id="rt-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus /></Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
