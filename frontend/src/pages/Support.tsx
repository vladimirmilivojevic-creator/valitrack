import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Empty, Field, Id, Loading, Modal, PageHeader, Panel, StatusChip } from "../components/ui";
import { api, errorMessage, qs } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDateTime } from "../lib/format";
import { useApplications, useUsers } from "../lib/queries";
import { TICKET_CATEGORIES } from "../lib/status";
import { useAct } from "../lib/toast";
import type { Ticket } from "../lib/types";

export default function Support() {
  const { can } = useAuth();
  const { applications, name: appName } = useApplications();
  const { name } = useUsers();
  const [scope, setScope] = useState("open");
  const [applicationId, setApplicationId] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["tickets", scope, applicationId],
    queryFn: () => api.get<Ticket[]>(`/tickets${qs({ open_only: scope === "open" ? true : undefined, application_id: applicationId })}`),
  });
  const rows = data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="User support"
        subtitle="Questions and problems from the people who use the applications. Second-level support works the tickets and links a change request when a fix needs one."
        actions={can("ticket.write") && <button className="btn btn--primary" onClick={() => setCreating(true)}><Plus size={16} aria-hidden="true" /> New ticket</button>}
      />
      <div className="row" style={{ marginBottom: 14 }}>
        <select className="select" style={{ width: 200 }} aria-label="Status filter" value={scope} onChange={(e) => setScope(e.target.value)}><option value="open">Open tickets</option><option value="all">All tickets</option></select>
        <select className="select" style={{ width: 220 }} aria-label="Application filter" value={applicationId} onChange={(e) => setApplicationId(e.target.value)}><option value="">All applications</option>{applications.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
      </div>
      <Panel flush>
        {isLoading ? <Loading /> : rows.length === 0 ? <Empty title="No tickets here" /> : (
          <div className="scroll-x">
            <table className="table table--hover">
              <thead><tr><th>Ticket</th><th>Application</th><th>Category</th><th>Priority</th><th>Status</th><th>Reported by</th><th>Assigned to</th></tr></thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id} onClick={() => setSelected(t.id)}>
                    <td><div className="title">{t.summary}</div><div className="sub"><Id>{t.code}</Id> · {fmtDateTime(t.created_at)}</div></td>
                    <td>{appName(t.application_id)}</td>
                    <td>{TICKET_CATEGORIES[t.category]}</td>
                    <td><StatusChip status={t.priority} /></td>
                    <td><StatusChip status={t.status} /></td>
                    <td>{name(t.reporter_id)}</td>
                    <td>{t.assignee_id ? name(t.assignee_id) : <span className="muted">nobody</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {selected && <TicketDialog id={selected} onClose={() => setSelected(null)} />}
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const { applications } = useApplications();
  const act = useAct();
  const [form, setForm] = useState({ application_id: applications[0]?.id ?? 0, summary: "", description: "", category: "how_to", priority: "normal" });
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try { await act(() => api.post("/tickets", form), "Ticket created."); onClose(); } catch (e) { setError(errorMessage(e)); }
  }
  return (
    <Modal title="New support ticket" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="ticket-form">Create</button></>}>
      <form id="ticket-form" onSubmit={submit}>
        <Field label="Application" htmlFor="k-app"><select id="k-app" className="select" value={form.application_id} onChange={(e) => setForm({ ...form, application_id: Number(e.target.value) })}>{applications.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
        <Field label="Summary" htmlFor="k-sum"><input id="k-sum" className="input" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} required autoFocus /></Field>
        <Field label="Details" htmlFor="k-desc"><textarea id="k-desc" className="textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></Field>
        <div className="fields-2">
          <Field label="Category" htmlFor="k-cat"><select id="k-cat" className="select" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{Object.entries(TICKET_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Priority" htmlFor="k-prio"><select id="k-prio" className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></Field>
        </div>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function TicketDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const { can } = useAuth();
  const { users, name } = useUsers();
  const act = useAct();
  const { data: ticket } = useQuery({ queryKey: ["ticket", id], queryFn: () => api.get<Ticket>(`/tickets/${id}`) });
  const [comment, setComment] = useState("");
  const [resolution, setResolution] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!ticket) return <Modal title="Ticket" onClose={onClose}><Loading /></Modal>;
  const manage = can("ticket.manage") && ticket.status !== "closed";
  const update = async (patch: Record<string, unknown>, message?: string) => {
    try { await act(() => api.patch(`/tickets/${ticket.id}`, patch), message); setError(null); } catch (e) { setError(errorMessage(e)); }
  };

  async function addComment(event: FormEvent) {
    event.preventDefault();
    try { await act(() => api.post(`/tickets/${ticket!.id}/comments`, { body: comment }), "Comment added."); setComment(""); } catch (e) { setError(errorMessage(e)); }
  }

  return (
    <Modal title={`${ticket.code}: ${ticket.summary}`} wide onClose={onClose}>
      <div className="row" style={{ marginBottom: 10 }}><StatusChip status={ticket.status} /><StatusChip status={ticket.priority} /><span className="muted small">{TICKET_CATEGORIES[ticket.category]} · reported by {name(ticket.reporter_id)} on {fmtDateTime(ticket.created_at)}</span></div>
      <p>{ticket.description}</p>
      {manage && (
        <div className="panel" style={{ padding: 14, marginBottom: 14 }}>
          <div className="fields-3">
            <Field label="Assigned to" htmlFor="tk-assign"><select id="tk-assign" className="select" value={ticket.assignee_id ?? ""} onChange={(e) => void update({ assignee_id: e.target.value ? Number(e.target.value) : null })}><option value="">Nobody</option>{users.filter((u) => ["validation_engineer", "admin"].includes(u.role)).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></Field>
            <Field label="Status" htmlFor="tk-status"><select id="tk-status" className="select" value={ticket.status} onChange={(e) => void update({ status: e.target.value, resolution: resolution ?? ticket.resolution }, "Ticket updated.")}><option value="open">Open</option><option value="in_progress">In progress</option><option value="waiting_user">Waiting for user</option><option value="resolved">Resolved</option><option value="closed">Closed</option></select></Field>
            <Field label="Priority" htmlFor="tk-prio"><select id="tk-prio" className="select" value={ticket.priority} onChange={(e) => void update({ priority: e.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></Field>
          </div>
          <Field label="Resolution" hint="Needed before the ticket is resolved or closed." htmlFor="tk-res"><textarea id="tk-res" className="textarea" style={{ minHeight: 56 }} value={resolution ?? ticket.resolution ?? ""} onChange={(e) => setResolution(e.target.value)} onBlur={() => resolution !== null && resolution !== ticket.resolution && void update({ resolution })} /></Field>
        </div>
      )}
      {!manage && ticket.resolution && <p><strong>Resolution:</strong> {ticket.resolution}</p>}
      <h3 style={{ margin: "6px 0 8px" }}>Conversation</h3>
      {ticket.comments.length === 0 && <p className="muted small">No comments yet.</p>}
      {ticket.comments.map((c) => (
        <div className="sig" key={c.id}><strong>{name(c.author_id)}</strong> <span className="muted small">{fmtDateTime(c.created_at)}</span><div>{c.body}</div></div>
      ))}
      {ticket.status !== "closed" && can("ticket.write") && (
        <form onSubmit={addComment} style={{ marginTop: 12 }}>
          <Field label="Add a comment" htmlFor="tk-comment"><textarea id="tk-comment" className="textarea" style={{ minHeight: 56 }} value={comment} onChange={(e) => setComment(e.target.value)} required /></Field>
          <button className="btn" type="submit">Add comment</button>
        </form>
      )}
      {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600, marginTop: 10 }}>{error}</p>}
    </Modal>
  );
}
