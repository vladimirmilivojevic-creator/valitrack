import { useQuery } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Banner, Empty, Field, Loading, Modal, Panel } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDateTime } from "../../lib/format";
import { useUsers } from "../../lib/queries";
import { useAct } from "../../lib/toast";
import type { Application, Change, ConfigItem } from "../../lib/types";

const OPEN_FOR_CONFIG = ["approved", "testing", "ready_for_release"];

export default function Config({ app }: { app: Application }) {
  const { can } = useAuth();
  const { name } = useUsers();
  const [editing, setEditing] = useState<ConfigItem | "new" | null>(null);
  const validated = !!app.live_version;
  const items = useQuery({ queryKey: ["config", app.id], queryFn: () => api.get<ConfigItem[]>(`/applications/${app.id}/config`) });
  const changes = useQuery({ queryKey: ["changes", "of-application", app.id], queryFn: () => api.get<Change[]>(`/changes?application_id=${app.id}`) });
  const eligible = (changes.data ?? []).filter((c) => OPEN_FOR_CONFIG.includes(c.status));
  const codeOf = (id: number | null) => changes.data?.find((c) => c.id === id)?.code ?? null;

  if (items.isLoading) return <Loading />;
  const rows = items.data ?? [];

  return (
    <div className="stack-lg">
      {validated && (
        <Banner tone="info">
          <p>
            This application has a validated version, so its configuration is part of the validated state. A setting can only be
            changed under an approved <Link to="/changes">change request</Link>.
          </p>
        </Banner>
      )}
      <Panel
        title={`Configuration baseline (${rows.length})`}
        flush
        actions={can("config.write") && <button className="btn btn--sm" onClick={() => setEditing("new")}><Plus size={14} aria-hidden="true" /> Add setting</button>}
      >
        {rows.length === 0 ? (
          <Empty title="No settings recorded">Record the settings that were configured, so a later change can be compared with them.</Empty>
        ) : (
          <div className="scroll-x">
            <table className="table">
              <thead><tr><th>Setting</th><th>Value</th><th>Last change</th><th>Updated</th><th /></tr></thead>
              <tbody>
                {rows.map((item) => (
                  <tr key={item.id}>
                    <td><div className="title">{item.name}</div><div className="sub">{item.description}</div></td>
                    <td className="mono">{item.value}</td>
                    <td>{item.last_change_request_id ? <Link to={`/changes/${item.last_change_request_id}`} className="id">{codeOf(item.last_change_request_id) ?? `CR #${item.last_change_request_id}`}</Link> : <span className="muted">initial</span>}</td>
                    <td className="small">{fmtDateTime(item.updated_at)}<div className="sub">{name(item.updated_by)}</div></td>
                    <td>{can("config.write") && <button className="btn btn--sm btn--ghost" onClick={() => setEditing(item)} aria-label={`Edit ${item.name}`}><Pencil size={14} /></button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {editing && <ConfigDialog app={app} item={editing === "new" ? null : editing} eligible={eligible} validated={validated} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ConfigDialog({ app, item, eligible, validated, onClose }: { app: Application; item: ConfigItem | null; eligible: Change[]; validated: boolean; onClose: () => void }) {
  const act = useAct();
  const [form, setForm] = useState({
    name: item?.name ?? "", value: item?.value ?? "", description: item?.description ?? "",
    change_request_id: (eligible[0]?.id ?? null) as number | null, reason: "",
  });
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const change = validated ? form.change_request_id : null;
    try {
      if (item) {
        await act(() => api.patch(`/config/${item.id}`, { value: form.value, description: form.description || null, change_request_id: change, reason: form.reason }), "Setting saved.");
      } else {
        await act(() => api.post(`/applications/${app.id}/config`, { name: form.name, value: form.value, description: form.description || null, change_request_id: change }), "Setting added.");
      }
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title={item ? `Edit ${item.name}` : "Add setting"} onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="config-form">Save</button></>}>
      <form id="config-form" onSubmit={submit}>
        {!item && <Field label="Setting" htmlFor="c-name"><input id="c-name" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus /></Field>}
        <Field label="Value" htmlFor="c-value"><input id="c-value" className="input" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required autoFocus={!!item} /></Field>
        <Field label="What it does (optional)" htmlFor="c-desc"><input id="c-desc" className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        {validated && (
          <Field label="Approved change request" hint={eligible.length ? "The change that allows this configuration change." : "There is no approved change for this application yet."} htmlFor="c-cr">
            <select id="c-cr" className="select" value={form.change_request_id ?? ""} onChange={(e) => setForm({ ...form, change_request_id: e.target.value ? Number(e.target.value) : null })} required>
              <option value="">Choose</option>
              {eligible.map((c) => <option key={c.id} value={c.id}>{c.code} {c.title}</option>)}
            </select>
          </Field>
        )}
        {item && <Field label="Reason for the change" htmlFor="c-reason"><input id="c-reason" className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required /></Field>}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
