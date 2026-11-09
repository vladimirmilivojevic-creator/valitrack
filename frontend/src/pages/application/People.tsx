import { useQuery } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Empty, Loading, Modal, Panel, StatusChip } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDate, titleCase } from "../../lib/format";
import { useUsers } from "../../lib/queries";
import { useAct } from "../../lib/toast";
import type { Application, MatrixRow } from "../../lib/types";

export default function People({ app }: { app: Application }) {
  const { can } = useAuth();
  const { users, name } = useUsers();
  const [editing, setEditing] = useState(false);
  const matrix = useQuery({ queryKey: ["training-matrix"], queryFn: () => api.get<MatrixRow[]>("/training/matrix") });
  if (matrix.isLoading) return <Loading />;
  const rows = (matrix.data ?? []).filter((r) => r.application_id === app.id);
  const assigned = app.users ?? [];
  const status = (userId: number) => rows.find((r) => r.user_id === userId);

  return (
    <Panel
      title={`Who uses ${app.name} (${assigned.length})`}
      flush
      actions={can("app.write") && <button className="btn btn--sm" onClick={() => setEditing(true)}><Pencil size={14} aria-hidden="true" /> Edit access list</button>}
    >
      {assigned.length === 0 ? (
        <Empty title="Nobody is assigned">The access list decides who must be trained when a new version is released.</Empty>
      ) : (
        <div className="scroll-x">
          <table className="table">
            <thead><tr><th>Person</th><th>Role in the application</th><th>Training on {app.live_version ? `v${app.live_version.version}` : "the live version"}</th><th>Trained on</th></tr></thead>
            <tbody>
              {assigned.map((a) => {
                const row = status(a.user_id);
                return (
                  <tr key={a.user_id}>
                    <td>{name(a.user_id)}<div className="sub">{users.find((u) => u.id === a.user_id)?.department}</div></td>
                    <td>{titleCase(a.app_role)}</td>
                    <td>{row ? <StatusChip status={row.training_status} /> : <span className="muted">no live version</span>}</td>
                    <td>{fmtDate(row?.completed_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="small muted" style={{ padding: "10px 16px 14px", margin: 0 }}>
        Training sessions and the full matrix are on the <Link to="/training">Training</Link> page.
      </p>
      {editing && <AccessDialog app={app} onClose={() => setEditing(false)} />}
    </Panel>
  );
}

function AccessDialog({ app, onClose }: { app: Application; onClose: () => void }) {
  const act = useAct();
  const { users } = useUsers();
  const [roles, setRoles] = useState<Record<number, string>>(() => Object.fromEntries((app.users ?? []).map((u) => [u.user_id, u.app_role])));

  async function save() {
    const assignments = Object.entries(roles).map(([id, app_role]) => ({ user_id: Number(id), app_role }));
    await act(() => api.put(`/applications/${app.id}/users`, { assignments }), "Access list saved.");
    onClose();
  }

  return (
    <Modal title="Access list" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" onClick={() => void save()}>Save</button></>}>
      {users.filter((u) => u.is_active).map((u) => (
        <div key={u.id} className="row" style={{ marginBottom: 8, flexWrap: "nowrap" }}>
          <label className="check grow" style={{ marginBottom: 0 }}>
            <input
              type="checkbox"
              checked={u.id in roles}
              onChange={(e) => setRoles((current) => {
                const next = { ...current };
                if (e.target.checked) next[u.id] = "user"; else delete next[u.id];
                return next;
              })}
            />
            <span>{u.full_name} <span className="muted small">{u.department}</span></span>
          </label>
          {u.id in roles && (
            <select className="select" style={{ width: 150 }} aria-label={`Role of ${u.full_name}`} value={roles[u.id]} onChange={(e) => setRoles({ ...roles, [u.id]: e.target.value })}>
              <option value="user">User</option><option value="key_user">Key user</option><option value="administrator">Administrator</option>
            </select>
          )}
        </div>
      ))}
    </Modal>
  );
}
