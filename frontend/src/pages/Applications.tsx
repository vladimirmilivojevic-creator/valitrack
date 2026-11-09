import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Empty, Field, Loading, Modal, PageHeader, Panel, RiskChip, StatusChip, Term } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApplications, useMeta, useUsers } from "../lib/queries";
import { useAct } from "../lib/toast";
import type { Application } from "../lib/types";

export default function Applications() {
  const { applications, isLoading } = useApplications();
  const { can } = useAuth();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        eyebrow="Validate"
        title="Applications"
        subtitle="Every software application that is validated and kept under change control."
        actions={
          can("app.write") && (
            <button className="btn btn--primary" onClick={() => setCreating(true)}>
              <Plus size={16} aria-hidden="true" /> New application
            </button>
          )
        }
      />
      <Panel flush>
        {isLoading ? (
          <Loading />
        ) : applications.length === 0 ? (
          <Empty title="No applications yet" />
        ) : (
          <div className="scroll-x">
            <table className="table">
              <thead>
                <tr>
                  <th>Application</th>
                  <th>
                    <Term k="GAMP">GAMP</Term> category
                  </th>
                  <th>Intended-use risk</th>
                  <th>Live version</th>
                  <th>In validation</th>
                  <th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <Link className="title" to={`/applications/${a.id}`}>
                        {a.name}
                      </Link>
                      <div className="sub">
                        <span className="id">{a.code}</span> · {a.vendor}
                      </div>
                    </td>
                    <td>
                      {a.gamp_category} <span className="muted small">{a.gamp_name}</span>
                    </td>
                    <td>
                      <RiskChip level={a.risk_class} />
                    </td>
                    <td>{a.live_version ? <StatusChip status="validated" label={`v${a.live_version.version}`} /> : <span className="muted">none yet</span>}</td>
                    <td>{a.working_version ? <StatusChip status="in_validation" label={`v${a.working_version.version}`} /> : <span className="muted">-</span>}</td>
                    <td>
                      {a.owner_name}
                      <div className="sub">{a.department}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const { data: meta } = useMeta();
  const { users } = useUsers();
  const { user } = useAuth();
  const act = useAct();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    description: "",
    vendor: "",
    department: "Quality Assurance",
    owner_id: user?.id ?? 0,
    gamp_category: 4,
    intended_use: "",
    patient_safety_impact: false,
    product_quality_impact: false,
    data_integrity_impact: false,
    initial_version: "1.0",
  });
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));
  const gamp = meta?.gamp[String(form.gamp_category)];

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const created = await act(() => api.post<Application>("/applications", form), "Application created.");
      onClose();
      navigate(`/applications/${created.id}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal
      title="New application"
      wide
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn--primary" type="submit" form="app-form">
            Create application
          </button>
        </>
      }
    >
      <form id="app-form" onSubmit={submit}>
        <div className="fields-2">
          <Field label="Name" htmlFor="a-name">
            <input id="a-name" className="input" value={form.name} onChange={(e) => set("name", e.target.value)} required autoFocus />
          </Field>
          <Field label="Vendor" htmlFor="a-vendor">
            <input id="a-vendor" className="input" value={form.vendor} onChange={(e) => set("vendor", e.target.value)} required />
          </Field>
        </div>
        <Field label="What is it?" htmlFor="a-desc">
          <input id="a-desc" className="input" value={form.description} onChange={(e) => set("description", e.target.value)} required />
        </Field>
        <Field label="Intended use" hint="What the application is used for. Validation proves it works for exactly this." htmlFor="a-use">
          <textarea id="a-use" className="textarea" value={form.intended_use} onChange={(e) => set("intended_use", e.target.value)} required />
        </Field>
        <div className="fields-3">
          <Field label="Business owner (department)" htmlFor="a-dept">
            <select id="a-dept" className="select" value={form.department} onChange={(e) => set("department", e.target.value)}>
              {meta?.departments.map((d) => <option key={d}>{d}</option>)}
            </select>
          </Field>
          <Field label="System owner" htmlFor="a-owner">
            <select id="a-owner" className="select" value={form.owner_id} onChange={(e) => set("owner_id", Number(e.target.value))}>
              {users.filter((u) => u.is_active).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </select>
          </Field>
          <Field label="First version" htmlFor="a-version">
            <input id="a-version" className="input" value={form.initial_version} onChange={(e) => set("initial_version", e.target.value)} required />
          </Field>
        </div>
        <Field label="GAMP software category" hint={gamp ? `${gamp.name}. ${gamp.summary}` : undefined} htmlFor="a-gamp">
          <select id="a-gamp" className="select" value={form.gamp_category} onChange={(e) => set("gamp_category", Number(e.target.value))}>
            {Object.entries(meta?.gamp ?? {}).map(([key, value]) => (
              <option key={key} value={key}>{key} - {value.name}</option>
            ))}
          </select>
        </Field>
        <div className="field">
          <span className="label">Could a failure of this application affect...</span>
          <label className="check"><input type="checkbox" checked={form.patient_safety_impact} onChange={(e) => set("patient_safety_impact", e.target.checked)} /> patient safety</label>
          <label className="check"><input type="checkbox" checked={form.product_quality_impact} onChange={(e) => set("product_quality_impact", e.target.checked)} /> product quality</label>
          <label className="check"><input type="checkbox" checked={form.data_integrity_impact} onChange={(e) => set("data_integrity_impact", e.target.checked)} /> data integrity (records, signatures, traceability)</label>
          <span className="hint">The answers set the intended-use risk: high, medium or low.</span>
        </div>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
