import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { SignatureModal } from "../components/Signing";
import { Empty, Field, Id, Loading, Modal, PageHeader, Panel, StatusChip } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate } from "../lib/format";
import { useApplications, useUsers } from "../lib/queries";
import { SESSION_TYPES } from "../lib/status";
import { useAct } from "../lib/toast";
import type { Application, MatrixRow, TrainingSession } from "../lib/types";

export default function Training() {
  const { can } = useAuth();
  const { applications, name: appName } = useApplications();
  const { name } = useUsers();
  const [onlyGaps, setOnlyGaps] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [completing, setCompleting] = useState<TrainingSession | null>(null);
  const act = useAct();
  const matrix = useQuery({ queryKey: ["training-matrix"], queryFn: () => api.get<MatrixRow[]>("/training/matrix") });
  const sessions = useQuery({ queryKey: ["training-sessions"], queryFn: () => api.get<TrainingSession[]>("/training/sessions") });

  if (matrix.isLoading || sessions.isLoading) return <Loading />;
  const rows = (matrix.data ?? []).filter((r) => !onlyGaps || ["not_trained", "retraining_needed"].includes(r.training_status));
  const byApp = new Map<number, MatrixRow[]>();
  for (const r of rows) byApp.set(r.application_id, [...(byApp.get(r.application_id) ?? []), r]);
  const gaps = (matrix.data ?? []).filter((r) => ["not_trained", "retraining_needed"].includes(r.training_status)).length;

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="Training"
        subtitle="Who has been trained on the version of each application that is live now. A new release makes everybody who knew the old version a candidate for retraining."
        actions={can("training.manage") && <button className="btn btn--primary" onClick={() => setScheduling(true)}><Plus size={16} aria-hidden="true" /> Schedule a session</button>}
      />

      <div className="grid-2">
        <Panel
          title={`Training matrix (${gaps} gaps)`}
          flush
          actions={<label className="check" style={{ margin: 0 }}><input type="checkbox" checked={onlyGaps} onChange={(e) => setOnlyGaps(e.target.checked)} /> Gaps only</label>}
        >
          {byApp.size === 0 ? <Empty title={onlyGaps ? "No gaps. Everybody is trained." : "No assigned users yet"} /> : (
            [...byApp.entries()].map(([applicationId, items]) => (
              <div key={applicationId}>
                <div style={{ padding: "10px 14px", background: "var(--sunken)", fontWeight: 650 }}>
                  {appName(applicationId)} <span className="muted" style={{ fontWeight: 500 }}>live version {items[0].live_version}</span>
                </div>
                <table className="table">
                  <tbody>
                    {items.map((r) => (
                      <tr key={r.user_id}>
                        <td>{r.full_name}<div className="sub">{r.department}</div></td>
                        <td><StatusChip status={r.training_status} /></td>
                        <td className="small">{r.completed_at ? `trained ${fmtDate(r.completed_at)}` : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))
          )}
        </Panel>

        <Panel title="Sessions" flush>
          {(sessions.data ?? []).length === 0 ? <Empty title="No sessions yet" /> : (
            <table className="table">
              <tbody>
                {(sessions.data ?? []).map((s) => {
                  const present = s.attendees.filter((a) => a.attended).length;
                  return (
                    <tr key={s.id}>
                      <td>
                        <div className="title">{s.title}</div>
                        <div className="sub"><Id>{s.code}</Id> · {appName(s.application_id)} · {SESSION_TYPES[s.session_type]} · {fmtDate(s.session_date)}</div>
                        <div className="sub">Trainer {name(s.trainer_id)} · {s.status === "completed" ? `${present} of ${s.attendees.length} present` : `${s.attendees.length} invited`}</div>
                      </td>
                      <td><StatusChip status={s.status} /></td>
                      <td>{s.status === "planned" && can("training.manage") && <button className="btn btn--sm" onClick={() => setCompleting(s)}>Complete</button>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      {scheduling && <ScheduleDialog applications={applications} onClose={() => setScheduling(false)} />}
      {completing && (
        <CompleteSession session={completing} onClose={() => setCompleting(null)} onSign={(password, attended) => act(() => api.post(`/training/sessions/${completing.id}/complete`, { password, attended_ids: attended }), "Session completed. Training records created.")} />
      )}
    </>
  );
}

function CompleteSession({ session, onClose, onSign }: { session: TrainingSession; onClose: () => void; onSign: (password: string, attended: number[]) => Promise<unknown> }) {
  const { name } = useUsers();
  const [present, setPresent] = useState<number[]>(session.attendees.map((a) => a.user_id));
  return (
    <SignatureModal
      title={`Complete ${session.code}`}
      meaning="Training verified"
      record={`${session.title} on ${fmtDate(session.session_date)}`}
      summary={
        <div className="field">
          <span className="label">Who took part?</span>
          {session.attendees.map((a) => (
            <label key={a.user_id} className="check"><input type="checkbox" checked={present.includes(a.user_id)} onChange={(e) => setPresent(e.target.checked ? [...present, a.user_id] : present.filter((x) => x !== a.user_id))} /> {name(a.user_id)}</label>
          ))}
          <span className="hint">Each person who was present gets a training record for this version.</span>
        </div>
      }
      onSign={(password) => onSign(password, present)}
      onClose={onClose}
    />
  );
}

function ScheduleDialog({ applications, onClose }: { applications: Application[]; onClose: () => void }) {
  const { users } = useUsers();
  const { user } = useAuth();
  const act = useAct();
  const [applicationId, setApplicationId] = useState(applications.find((a) => a.live_version)?.id ?? applications[0]?.id ?? 0);
  const detail = useQuery({ queryKey: ["application", String(applicationId)], enabled: applicationId > 0, queryFn: () => api.get<Application>(`/applications/${applicationId}`) });
  const versions = [detail.data?.live_version, detail.data?.working_version].filter((v): v is NonNullable<typeof v> => !!v);
  const [form, setForm] = useState({ app_version_id: 0, title: "", session_type: "classroom", trainer_id: user?.id ?? 0, session_date: new Date().toISOString().slice(0, 10), duration_minutes: 60, materials: "" });
  const [attendees, setAttendees] = useState<number[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const assigned = (detail.data?.users ?? []).map((u) => u.user_id);
  const chosen = attendees ?? assigned;
  const versionId = form.app_version_id || versions[0]?.id || 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await act(() => api.post("/training/sessions", { ...form, application_id: applicationId, app_version_id: versionId, materials: form.materials || null, attendee_ids: chosen }), "Session scheduled.");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title="Schedule a training session" wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="session-form">Schedule</button></>}>
      <form id="session-form" onSubmit={submit}>
        <div className="fields-2">
          <Field label="Application" htmlFor="s-app"><select id="s-app" className="select" value={applicationId} onChange={(e) => { setApplicationId(Number(e.target.value)); setAttendees(null); setForm({ ...form, app_version_id: 0 }); }}>{applications.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
          <Field label="Version" htmlFor="s-version"><select id="s-version" className="select" value={versionId} onChange={(e) => setForm({ ...form, app_version_id: Number(e.target.value) })}>{versions.map((v) => <option key={v.id} value={v.id}>{v.version} ({v.status.replace("_", " ")})</option>)}</select></Field>
        </div>
        <Field label="Title" htmlFor="s-title"><input id="s-title" className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required autoFocus /></Field>
        <div className="fields-3">
          <Field label="Type" htmlFor="s-type"><select id="s-type" className="select" value={form.session_type} onChange={(e) => setForm({ ...form, session_type: e.target.value })}>{Object.entries(SESSION_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Date" htmlFor="s-date"><input id="s-date" className="input" type="date" value={form.session_date} onChange={(e) => setForm({ ...form, session_date: e.target.value })} required /></Field>
          <Field label="Minutes" htmlFor="s-min"><input id="s-min" className="input" type="number" min={5} value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })} /></Field>
        </div>
        <Field label="Trainer" htmlFor="s-trainer"><select id="s-trainer" className="select" value={form.trainer_id} onChange={(e) => setForm({ ...form, trainer_id: Number(e.target.value) })}>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></Field>
        <Field label="Material (optional)" htmlFor="s-mat"><input id="s-mat" className="input" value={form.materials} onChange={(e) => setForm({ ...form, materials: e.target.value })} /></Field>
        <div className="field">
          <span className="label">Invited ({chosen.length})</span>
          {users.filter((u) => u.is_active).map((u) => (
            <label key={u.id} className="check"><input type="checkbox" checked={chosen.includes(u.id)} onChange={(e) => setAttendees(e.target.checked ? [...chosen, u.id] : chosen.filter((x) => x !== u.id))} /> {u.full_name} <span className="muted small">{u.department}</span></label>
          ))}
        </div>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
