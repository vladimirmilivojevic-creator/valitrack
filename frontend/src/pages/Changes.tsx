import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Empty, Field, Id, Loading, Modal, PageHeader, Panel, RiskChip, StatusChip, Term } from "../components/ui";
import { api, errorMessage, qs } from "../lib/api";
import { useAuth } from "../lib/auth";
import { daysFromToday, fmtDate } from "../lib/format";
import { useApplications, useUsers } from "../lib/queries";
import { CHANGE_TYPES } from "../lib/status";
import { useAct } from "../lib/toast";
import type { Change } from "../lib/types";

export default function Changes() {
  const { can } = useAuth();
  const { applications } = useApplications();
  const { name } = useUsers();
  const [scope, setScope] = useState("open");
  const [applicationId, setApplicationId] = useState("");
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["changes", scope, applicationId],
    queryFn: () => api.get<Change[]>(`/changes${qs({ open_only: scope === "open" ? true : undefined, status: scope !== "open" && scope !== "all" ? scope : undefined, application_id: applicationId })}`),
  });
  const rows = data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Change"
        title="Change control"
        subtitle="No change to a validated application happens without a request, an impact assessment by the departments, an approval and a test."
        actions={can("change.create") && <button className="btn btn--primary" onClick={() => setCreating(true)}><Plus size={16} aria-hidden="true" /> New change request</button>}
      />
      <div className="row" style={{ marginBottom: 14 }}>
        <select className="select" style={{ width: 220 }} aria-label="Status filter" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="open">Open changes</option>
          <option value="all">All changes</option>
          <option value="released">Released</option>
          <option value="rejected">Rejected</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select className="select" style={{ width: 220 }} aria-label="Application filter" value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
          <option value="">All applications</option>
          {applications.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <Panel flush>
        {isLoading ? <Loading /> : rows.length === 0 ? <Empty title="No changes here" /> : (
          <div className="scroll-x">
            <table className="table table--hover">
              <thead><tr><th>Change</th><th>Application</th><th>Type</th><th>Status</th><th>Risk</th><th>Requested by</th><th>Target</th><th>Planned release</th></tr></thead>
              <tbody>
                {rows.map((c) => {
                  const days = daysFromToday(c.planned_release_date);
                  return (
                    <tr key={c.id}>
                      <td><Link to={`/changes/${c.id}`} className="title">{c.title}</Link><div className="sub"><Id>{c.code}</Id></div></td>
                      <td>{c.application_name}</td>
                      <td>{CHANGE_TYPES[c.change_type]}</td>
                      <td><StatusChip status={c.status} /></td>
                      <td><RiskChip level={c.risk_level} /></td>
                      <td>{name(c.requested_by)}</td>
                      <td className="mono">{c.target_version}</td>
                      <td>{fmtDate(c.planned_release_date)}{days !== null && c.status !== "released" && <div className="sub">{days >= 0 ? `in ${days} days` : `${-days} days ago`}</div>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <p className="small muted" style={{ marginTop: 12 }}>
        <Term k="Change control">Change control</Term> keeps a validated system in a validated state: every change is assessed, approved, tested and signed.
      </p>
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const { applications } = useApplications();
  const act = useAct();
  const navigate = useNavigate();
  const live = applications.filter((a) => a.live_version);
  const [form, setForm] = useState({
    application_id: live[0]?.id ?? 0, title: "", change_type: "enhancement", business_need: "", description: "",
    priority: "normal", target_version: "", planned_release_date: "", affects_requirements: false,
  });
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await act(() => api.post<Change>("/changes", { ...form, application_id: Number(form.application_id), planned_release_date: form.planned_release_date || null }), "Change request created.");
      onClose();
      navigate(`/changes/${created.id}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title="New change request" wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="change-form">Create draft</button></>}>
      <form id="change-form" onSubmit={submit}>
        <div className="fields-2">
          <Field label="Application" hint="Only validated applications are under change control." htmlFor="c-app">
            <select id="c-app" className="select" value={form.application_id} onChange={(e) => setForm({ ...form, application_id: Number(e.target.value) })}>
              {live.map((a) => <option key={a.id} value={a.id}>{a.name} (v{a.live_version?.version})</option>)}
            </select>
          </Field>
          <Field label="Type of change" htmlFor="c-type">
            <select id="c-type" className="select" value={form.change_type} onChange={(e) => setForm({ ...form, change_type: e.target.value })}>
              {Object.entries(CHANGE_TYPES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Title" htmlFor="c-title"><input id="c-title" className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required autoFocus /></Field>
        <Field label="Business need" hint="Why is this change wanted?" htmlFor="c-need"><textarea id="c-need" className="textarea" style={{ minHeight: 60 }} value={form.business_need} onChange={(e) => setForm({ ...form, business_need: e.target.value })} required /></Field>
        <Field label="What will change" htmlFor="c-desc"><textarea id="c-desc" className="textarea" style={{ minHeight: 60 }} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></Field>
        <div className="fields-3">
          <Field label="New version number" htmlFor="c-target"><input id="c-target" className="input" value={form.target_version} onChange={(e) => setForm({ ...form, target_version: e.target.value })} required /></Field>
          <Field label="Priority" htmlFor="c-prio">
            <select id="c-prio" className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
            </select>
          </Field>
          <Field label="Planned release (optional)" htmlFor="c-date"><input id="c-date" className="input" type="date" value={form.planned_release_date} onChange={(e) => setForm({ ...form, planned_release_date: e.target.value })} /></Field>
        </div>
        <label className="check"><input type="checkbox" checked={form.affects_requirements} onChange={(e) => setForm({ ...form, affects_requirements: e.target.checked })} /> The change adds or changes user requirements, so the requirements must be approved again</label>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
