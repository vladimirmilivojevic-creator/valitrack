import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { History } from "../components/History";
import { SignatureList, SignatureModal } from "../components/Signing";
import { Empty, Field, Id, Loading, Modal, PageHeader, Panel, StatusChip, Term } from "../components/ui";
import { api, errorMessage, qs } from "../lib/api";
import { useAuth } from "../lib/auth";
import { daysFromToday, fmtDate } from "../lib/format";
import { useApplications, useUsers } from "../lib/queries";
import { useAct } from "../lib/toast";
import type { Deviation } from "../lib/types";

export default function Deviations() {
  const { can } = useAuth();
  const { applications, name: appName } = useApplications();
  const { name } = useUsers();
  const [scope, setScope] = useState("open");
  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["deviations", scope],
    queryFn: () => api.get<Deviation[]>(`/deviations${qs({ status: scope === "all" ? undefined : scope })}`),
  });
  const rows = data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Validate"
        title="Deviations"
        subtitle={<>A <Term k="Deviation">deviation</Term> is anything that did not go as planned, for example a failed test. Each one gets a root cause and a <Term k="CAPA">corrective and preventive action</Term>, and QA closes it.</>}
        actions={can("deviation.write") && <button className="btn btn--primary" onClick={() => setCreating(true)}><Plus size={16} aria-hidden="true" /> Raise a deviation</button>}
      />
      <div className="row" style={{ marginBottom: 14 }}>
        <select className="select" style={{ width: 200 }} aria-label="Status filter" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="open">Open</option><option value="all">All</option><option value="closed">Closed</option><option value="accepted">Accepted</option>
        </select>
      </div>
      <Panel flush>
        {isLoading ? <Loading /> : rows.length === 0 ? <Empty title="No deviations here" /> : (
          <div className="scroll-x">
            <table className="table table--hover">
              <thead><tr><th>Deviation</th><th>Application</th><th>Severity</th><th>Status</th><th>Owner</th><th>Due</th></tr></thead>
              <tbody>
                {rows.map((d) => {
                  const days = daysFromToday(d.due_date);
                  const overdue = days !== null && days < 0 && ["open", "in_progress", "resolved"].includes(d.status);
                  return (
                    <tr key={d.id} onClick={() => setSelected(d.id)}>
                      <td><div className="title">{d.title}</div><div className="sub"><Id>{d.code}</Id> · {d.source === "test_failure" ? "opened by a failed test" : "raised manually"}</div></td>
                      <td>{appName(d.application_id)}</td>
                      <td><StatusChip status={d.severity} /></td>
                      <td><StatusChip status={d.status} /></td>
                      <td>{name(d.owner_id)}</td>
                      <td>{fmtDate(d.due_date)}{overdue && <div className="sub" style={{ color: "var(--fail)", fontWeight: 600 }}>{-days!} days overdue</div>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {selected && <DeviationDialog id={selected} onClose={() => setSelected(null)} />}
      {creating && <CreateDialog applications={applications.map((a) => ({ id: a.id, name: a.name }))} onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateDialog({ applications, onClose }: { applications: { id: number; name: string }[]; onClose: () => void }) {
  const act = useAct();
  const [form, setForm] = useState({ application_id: applications[0]?.id ?? 0, title: "", description: "", severity: "minor" });
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await act(() => api.post("/deviations", form), "Deviation raised."); onClose(); } catch (e) { setError(errorMessage(e)); }
  }
  return (
    <Modal title="Raise a deviation" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="dev-form">Raise</button></>}>
      <form id="dev-form" onSubmit={submit}>
        <Field label="Application" htmlFor="d-app"><select id="d-app" className="select" value={form.application_id} onChange={(e) => setForm({ ...form, application_id: Number(e.target.value) })}>{applications.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
        <Field label="Title" htmlFor="d-title"><input id="d-title" className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required autoFocus /></Field>
        <Field label="What happened?" htmlFor="d-desc"><textarea id="d-desc" className="textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></Field>
        <Field label="Severity" htmlFor="d-sev"><select id="d-sev" className="select" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}><option value="minor">Minor</option><option value="major">Major</option><option value="critical">Critical</option></select></Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function DeviationDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const { can } = useAuth();
  const { users, name } = useUsers();
  const act = useAct();
  const { data: d } = useQuery({ queryKey: ["deviation", id], queryFn: () => api.get<Deviation>(`/deviations/${id}`) });
  const [form, setForm] = useState<{ root_cause: string; impact: string; corrective_action: string; preventive_action: string; owner_id: number | null; due_date: string; reason: string } | null>(null);
  const [signing, setSigning] = useState<"close" | "accept" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!d) return <Modal title="Deviation" onClose={onClose}><Loading /></Modal>;
  const closed = d.status === "closed" || d.status === "accepted";
  const f = form ?? { root_cause: d.root_cause ?? "", impact: d.impact ?? "", corrective_action: d.corrective_action ?? "", preventive_action: d.preventive_action ?? "", owner_id: d.owner_id, due_date: d.due_date ?? "", reason: "" };
  const edit = (patch: Partial<typeof f>) => setForm({ ...f, ...patch });
  const canEdit = can("deviation.write") && !closed;

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await act(() => api.patch(`/deviations/${d!.id}`, { root_cause: f.root_cause || null, impact: f.impact || null, corrective_action: f.corrective_action || null, preventive_action: f.preventive_action || null, owner_id: f.owner_id, due_date: f.due_date || null, reason: f.reason }), "Deviation saved.");
      setForm(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title={`${d.code}: ${d.title}`} wide onClose={onClose}>
      <div className="row" style={{ marginBottom: 10 }}>
        <StatusChip status={d.status} /><StatusChip status={d.severity} />
        {d.test_run_id && <Link to={`/runs/${d.test_run_id}`}>Open the failed run</Link>}
      </div>
      <p>{d.description}</p>
      <form onSubmit={save}>
        <div className="fields-2">
          <Field label="Root cause" htmlFor="x-root"><textarea id="x-root" className="textarea" readOnly={!canEdit} value={f.root_cause} onChange={(e) => edit({ root_cause: e.target.value })} /></Field>
          <Field label="Impact" htmlFor="x-impact"><textarea id="x-impact" className="textarea" readOnly={!canEdit} value={f.impact} onChange={(e) => edit({ impact: e.target.value })} /></Field>
          <Field label="Corrective action (fix it now)" htmlFor="x-corr"><textarea id="x-corr" className="textarea" readOnly={!canEdit} value={f.corrective_action} onChange={(e) => edit({ corrective_action: e.target.value })} /></Field>
          <Field label="Preventive action (so it does not return)" htmlFor="x-prev"><textarea id="x-prev" className="textarea" readOnly={!canEdit} value={f.preventive_action} onChange={(e) => edit({ preventive_action: e.target.value })} /></Field>
          <Field label="Owner" htmlFor="x-owner"><select id="x-owner" className="select" disabled={!canEdit} value={f.owner_id ?? ""} onChange={(e) => edit({ owner_id: Number(e.target.value) })}>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></Field>
          <Field label="Due date" htmlFor="x-due"><input id="x-due" className="input" type="date" readOnly={!canEdit} value={f.due_date} onChange={(e) => edit({ due_date: e.target.value })} /></Field>
        </div>
        {canEdit && form && <Field label="Reason for the change" htmlFor="x-reason"><input id="x-reason" className="input" value={f.reason} onChange={(e) => edit({ reason: e.target.value })} required /></Field>}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
        <div className="row" style={{ marginBottom: 14 }}>
          {canEdit && form && <button className="btn btn--primary" type="submit">Save</button>}
          {can("deviation.write") && ["open", "in_progress"].includes(d.status) && <button type="button" className="btn" onClick={() => void act(() => api.post(`/deviations/${d.id}/resolve`), "Marked as resolved.").catch(() => undefined)}>Mark as resolved</button>}
          {can("deviation.close") && d.status === "resolved" && <button type="button" className="btn btn--primary" onClick={() => setSigning("close")}>Close with signature</button>}
          {can("deviation.close") && !closed && <button type="button" className="btn" onClick={() => setSigning("accept")}>Accept without a fix</button>}
        </div>
      </form>
      <h3 style={{ margin: "10px 0" }}>Signatures</h3>
      <SignatureList signatures={d.signatures} empty="Not closed yet. QA signs when the deviation is closed or accepted." />
      {d.closure_comment && <p className="small">Closure: {d.closure_comment}{d.closed_at ? ` (${fmtDate(d.closed_at)}, ${name(d.owner_id)} owner)` : ""}</p>}
      <h3 style={{ margin: "14px 0 6px" }}>History</h3>
      <History entityType="deviation" entityId={d.id} />
      {signing === "close" && <SignatureModal title="Close the deviation" meaning="Closed" record={`${d.code}: ${d.title}`} commentLabel="Closure comment" commentRequired onSign={(password, comment) => act(() => api.post(`/deviations/${d.id}/close`, { password, comment }), "Deviation closed.")} onClose={() => setSigning(null)} />}
      {signing === "accept" && <SignatureModal title="Accept the deviation" meaning="Approved" record={`${d.code}: ${d.title} accepted without a fix`} commentLabel="Justification" commentRequired summary={<p className="small">Explain why the deviation has no impact on the intended use. The justification is part of the signed record.</p>} onSign={(password, comment) => act(() => api.post(`/deviations/${d.id}/accept`, { password, comment }), "Deviation accepted.")} onClose={() => setSigning(null)} />}
    </Modal>
  );
}
