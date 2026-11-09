import { useQuery } from "@tanstack/react-query";
import { FileText, Pencil, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { GateChecklist } from "../../components/Gate";
import { SignatureModal } from "../../components/Signing";
import { Banner, Empty, Field, Loading, Modal, Panel, RiskChip, StatusChip, Term } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDate, fmtDateTime } from "../../lib/format";
import { useMeta, useUsers } from "../../lib/queries";
import { useAct } from "../../lib/toast";
import type { Application, Change, Gate, ReportDoc, Version } from "../../lib/types";

type Signing = { kind: "urs" | "release" } | { kind: "report"; doc: ReportDoc } | null;

export default function Overview({ app }: { app: Application }) {
  const { can, user } = useAuth();
  const { name } = useUsers();
  const { data: meta } = useMeta();
  const act = useAct();
  const version = app.working_version;
  const [signing, setSigning] = useState<Signing>(null);
  const [newVersion, setNewVersion] = useState(false);
  const [editing, setEditing] = useState(false);

  const gate = useQuery({
    queryKey: ["gate", version?.id],
    enabled: !!version,
    queryFn: () => api.get<Gate>(`/versions/${version!.id}/gate`),
  });
  const reports = useQuery({
    queryKey: ["report-docs", version?.id],
    enabled: !!version,
    queryFn: () => api.get<ReportDoc[]>(`/versions/${version!.id}/reports`),
  });
  const liveReports = useQuery({
    queryKey: ["report-docs", app.live_version?.id],
    enabled: !!app.live_version,
    queryFn: () => api.get<ReportDoc[]>(`/versions/${app.live_version!.id}/reports`),
  });
  const changes = useQuery({
    queryKey: ["changes", "of-application", app.id],
    queryFn: () => api.get<Change[]>(`/changes?application_id=${app.id}`),
  });
  const owningChange = version ? changes.data?.find((c) => c.target_version_id === version.id && c.status !== "cancelled") : undefined;
  const liveApproved = liveReports.data?.find((d) => d.status === "approved");
  const flags = [
    app.patient_safety_impact && "patient safety",
    app.product_quality_impact && "product quality",
    app.data_integrity_impact && "data integrity",
  ].filter(Boolean);

  const drafts = (reports.data ?? []).filter((d) => d.status !== "superseded");

  return (
    <div className="grid-2">
      <div className="stack-lg">
        <Panel
          title="About this application"
          actions={
            can("app.write") && (
              <button className="btn btn--sm" onClick={() => setEditing(true)}>
                <Pencil size={14} aria-hidden="true" /> Edit
              </button>
            )
          }
        >
          <dl className="kv">
            <dt>Intended use</dt>
            <dd>{app.intended_use}</dd>
            <dt>What it is</dt>
            <dd>{app.description}</dd>
            <dt>Vendor</dt>
            <dd>{app.vendor}</dd>
            <dt>Owner</dt>
            <dd>{app.owner_name} · {app.department}</dd>
            <dt>Could affect</dt>
            <dd>{flags.length ? flags.join(", ") : "nothing regulated"} <RiskChip level={app.risk_class} /></dd>
          </dl>
        </Panel>

        <Panel title="Validation approach">
          <p>{app.approach}</p>
          <div className="row">
            <span className="muted small">Required test types:</span>
            {app.required_tests.map((t) => (
              <Term key={t} k={t} />
            ))}
          </div>
          {meta && (
            <p className="small muted" style={{ marginTop: 10, marginBottom: 0 }}>
              {Object.entries(meta.test_types).filter(([k]) => app.required_tests.includes(k)).map(([k, v]) => `${k}: ${v}`).join(" ")}
            </p>
          )}
        </Panel>

        <Panel
          title="Versions"
          flush
          actions={
            can("app.write") && !app.live_version && !version && (
              <button className="btn btn--sm" onClick={() => setNewVersion(true)}>
                <Plus size={14} aria-hidden="true" /> New version
              </button>
            )
          }
        >
          {(app.versions ?? []).length === 0 ? (
            <Empty title="No versions yet" />
          ) : (
            <table className="table">
              <thead>
                <tr><th>Version</th><th>Status</th><th>Requirements</th><th>Validated</th></tr>
              </thead>
              <tbody>
                {app.versions!.map((v) => (
                  <tr key={v.id}>
                    <td className="mono title">{v.version}{v.release_notes && <div className="sub" style={{ fontFamily: "var(--font)" }}>{v.release_notes}</div>}</td>
                    <td><StatusChip status={v.status} /></td>
                    <td>{v.urs_approved ? `approved ${fmtDate(v.urs_approved_at)}` : <span className="muted">not approved</span>}</td>
                    <td>{fmtDate(v.validated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {app.live_version && (
            <p className="small muted" style={{ padding: "10px 16px 14px", margin: 0 }}>
              Changes to the validated version go through <Link to="/changes">change control</Link>.
              {liveApproved && (
                <> Approved report: <a href={`/api/report-documents/${liveApproved.id}/pdf`} target="_blank" rel="noreferrer">{liveApproved.doc_number} (PDF)</a>.</>
              )}
            </p>
          )}
        </Panel>
      </div>

      <div className="stack-lg">
        {version ? (
          <Panel title={`Release gate for version ${version.version}`}>
            {gate.isLoading || !gate.data ? <Loading /> : <GateChecklist gate={gate.data} />}
            <hr style={{ border: 0, borderTop: "1px solid var(--rule)", margin: "14px 0" }} />
            <div className="stack">
              {!version.urs_approved && gate.data && can("req.approve") && (
                <button className="btn" onClick={() => setSigning({ kind: "urs" })}>
                  Approve the requirements (URS)
                </button>
              )}
              {can("report.generate") && (
                <button className="btn" onClick={() => void act(() => api.post(`/versions/${version.id}/reports`), "Report generated.")}>
                  <FileText size={15} aria-hidden="true" /> Generate validation report
                </button>
              )}
              {drafts.map((doc) => (
                <div key={doc.id} className="row" style={{ justifyContent: "space-between" }}>
                  <span>
                    <a href={`/api/report-documents/${doc.id}/pdf`} target="_blank" rel="noreferrer" className="id">{doc.doc_number}</a>{" "}
                    <StatusChip status={doc.status} /> <span className="muted small">{fmtDateTime(doc.generated_at)} by {name(doc.generated_by)}</span>
                  </span>
                  {doc.status === "draft" && can("report.approve") && doc.generated_by !== user?.id && gate.data?.ready_for_report && (
                    <button className="btn btn--sm" onClick={() => setSigning({ kind: "report", doc })}>Approve report</button>
                  )}
                </div>
              ))}
              {owningChange ? (
                <p className="small muted" style={{ margin: 0 }}>
                  This version belongs to change <Link to={`/changes/${owningChange.id}`}>{owningChange.code}</Link>. It is tested and released there.
                </p>
              ) : (
                can("change.release") && gate.data?.passed && <ReleaseHint version={version} onRelease={() => setSigning({ kind: "release" })} />
              )}
            </div>
          </Panel>
        ) : (
          <Banner tone="info">
            <p>
              <strong>No version is in validation.</strong>{" "}
              {app.live_version ? (
                <>Version {app.live_version.version} is live. To change the application, start a <Link to="/changes">change request</Link>.</>
              ) : (
                "Create the first version to start the validation."
              )}
            </p>
          </Banner>
        )}
      </div>

      {signing?.kind === "urs" && version && (
        <SignatureModal
          title="Approve the requirements"
          meaning="Approved"
          record={`${app.name} ${version.version}: requirements baseline`}
          summary={<p className="small">After the approval the requirements are locked as a baseline. If one changes later, the release gate shows it and the baseline must be approved again.</p>}
          onSign={(password, comment) => act(() => api.post(`/versions/${version.id}/approve-urs`, { password, comment }), "Requirements approved.")}
          onClose={() => setSigning(null)}
        />
      )}
      {signing?.kind === "report" && (
        <SignatureModal
          title="Approve the validation report"
          meaning="Approved"
          record={`${signing.doc.doc_number} for ${app.name} ${version?.version}`}
          summary={<p className="small">The signature covers the exact PDF (SHA-256 <span className="hash">{signing.doc.sha256.slice(0, 16)}</span>). If results change afterwards, the report becomes out of date.</p>}
          onSign={(password, comment) => act(() => api.post(`/report-documents/${signing.doc.id}/approve`, { password, comment }), "Report approved.")}
          onClose={() => setSigning(null)}
        />
      )}
      {signing?.kind === "release" && version && (
        <SignatureModal
          title={`Release version ${version.version}`}
          meaning="Released"
          record={`${app.name} ${version.version} becomes the validated version`}
          onSign={(password, comment) => act(() => api.post(`/versions/${version.id}/release`, { password, comment }), "Version released.")}
          onClose={() => setSigning(null)}
        />
      )}
      {newVersion && <NewVersionDialog app={app} onClose={() => setNewVersion(false)} />}
      {editing && <EditDialog app={app} onClose={() => setEditing(false)} />}
    </div>
  );
}

function ReleaseHint({ version, onRelease }: { version: Version; onRelease: () => void }) {
  return (
    <button className="btn btn--primary" onClick={onRelease}>
      Release version {version.version}
    </button>
  );
}

function NewVersionDialog({ app, onClose }: { app: Application; onClose: () => void }) {
  const act = useAct();
  const [version, setVersion] = useState("1.0");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await act(() => api.post(`/applications/${app.id}/versions`, { version, release_notes: notes || null }), "Version created.");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  return (
    <Modal title="New version" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="version-form">Create</button></>}>
      <form id="version-form" onSubmit={submit}>
        <Field label="Version number" htmlFor="v-no"><input id="v-no" className="input" value={version} onChange={(e) => setVersion(e.target.value)} required autoFocus /></Field>
        <Field label="Release notes (optional)" htmlFor="v-notes"><textarea id="v-notes" className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function EditDialog({ app, onClose }: { app: Application; onClose: () => void }) {
  const act = useAct();
  const { data: meta } = useMeta();
  const { users } = useUsers();
  const [form, setForm] = useState({
    description: app.description, vendor: app.vendor, intended_use: app.intended_use, owner_id: app.owner_id,
    department: app.department, patient_safety_impact: app.patient_safety_impact,
    product_quality_impact: app.product_quality_impact, data_integrity_impact: app.data_integrity_impact, reason: "",
  });
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await act(() => api.patch(`/applications/${app.id}`, form), "Application updated.");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  return (
    <Modal title="Edit application" wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="edit-app-form">Save</button></>}>
      <form id="edit-app-form" onSubmit={submit}>
        <Field label="Intended use" htmlFor="e-use"><textarea id="e-use" className="textarea" value={form.intended_use} onChange={(e) => setForm({ ...form, intended_use: e.target.value })} /></Field>
        <div className="fields-2">
          <Field label="What it is" htmlFor="e-desc"><input id="e-desc" className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Vendor" htmlFor="e-vendor"><input id="e-vendor" className="input" value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} /></Field>
          <Field label="Business owner (department)" htmlFor="e-dept">
            <select id="e-dept" className="select" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>{meta?.departments.map((d) => <option key={d}>{d}</option>)}</select>
          </Field>
          <Field label="System owner" htmlFor="e-owner">
            <select id="e-owner" className="select" value={form.owner_id} onChange={(e) => setForm({ ...form, owner_id: Number(e.target.value) })}>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select>
          </Field>
        </div>
        <label className="check"><input type="checkbox" checked={form.patient_safety_impact} onChange={(e) => setForm({ ...form, patient_safety_impact: e.target.checked })} /> Could affect patient safety</label>
        <label className="check"><input type="checkbox" checked={form.product_quality_impact} onChange={(e) => setForm({ ...form, product_quality_impact: e.target.checked })} /> Could affect product quality</label>
        <label className="check"><input type="checkbox" checked={form.data_integrity_impact} onChange={(e) => setForm({ ...form, data_integrity_impact: e.target.checked })} /> Could affect data integrity</label>
        <Field label="Reason for the change" hint="Goes into the audit trail." htmlFor="e-reason"><input id="e-reason" className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required /></Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
