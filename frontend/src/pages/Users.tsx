import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Chip, Field, Loading, Modal, PageHeader, Panel, StatusChip } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDateTime } from "../lib/format";
import { useMeta, useUsers } from "../lib/queries";
import { useAct } from "../lib/toast";
import type { User } from "../lib/types";

export default function Users() {
  const { users, isLoading } = useUsers();
  const { data: meta } = useMeta();
  const { user: me } = useAuth();
  const act = useAct();
  const [editing, setEditing] = useState<User | "new" | null>(null);

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Users"
        subtitle="Accounts are never deleted, because the audit trail refers to them. A person who leaves is deactivated."
        actions={<button className="btn btn--primary" onClick={() => setEditing("new")}><Plus size={16} aria-hidden="true" /> New user</button>}
      />
      <Panel flush>
        {isLoading ? <Loading /> : (
          <div className="scroll-x">
            <table className="table">
              <thead><tr><th>Person</th><th>Role</th><th>Department</th><th>Last sign-in</th><th>Status</th><th /></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td><div className="title">{u.full_name}</div><div className="sub mono">{u.username}</div></td>
                    <td>{meta?.roles[u.role] ?? u.role}</td>
                    <td>{u.department}</td>
                    <td>{fmtDateTime(u.last_login_at)}</td>
                    <td>{!u.is_active ? <StatusChip status="retired" label="Deactivated" /> : u.locked ? <Chip tone="warn">Locked</Chip> : <StatusChip status="active" />}</td>
                    <td className="nowrap">
                      <button className="btn btn--sm" onClick={() => setEditing(u)}>Edit</button>{" "}
                      {u.locked && <button className="btn btn--sm" onClick={() => void act(() => api.post(`/users/${u.id}/unlock`), "Account unlocked.")}>Unlock</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {editing && <UserDialog user={editing === "new" ? null : editing} isSelf={editing !== "new" && editing.id === me?.id} onClose={() => setEditing(null)} />}
    </>
  );
}

function UserDialog({ user, isSelf, onClose }: { user: User | null; isSelf: boolean; onClose: () => void }) {
  const { data: meta } = useMeta();
  const act = useAct();
  const [form, setForm] = useState({ username: user?.username ?? "", full_name: user?.full_name ?? "", email: user?.email ?? "", role: user?.role ?? "tester", department: user?.department ?? "Quality Assurance", password: "", is_active: user?.is_active ?? true });
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (user) {
        await act(() => api.patch(`/users/${user.id}`, { full_name: form.full_name, email: form.email, role: form.role, department: form.department, is_active: form.is_active }), "User saved.");
        if (form.password) await act(() => api.post(`/users/${user.id}/reset-password`, { new_password: form.password }), "Password reset.");
      } else {
        await act(() => api.post("/users", form), "User created.");
      }
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title={user ? `Edit ${user.full_name}` : "New user"} onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="user-form">Save</button></>}>
      <form id="user-form" onSubmit={submit}>
        {!user && <Field label="User name" htmlFor="u-name"><input id="u-name" className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required autoFocus /></Field>}
        <Field label="Full name" htmlFor="u-full"><input id="u-full" className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></Field>
        <Field label="Email" htmlFor="u-mail"><input id="u-mail" className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></Field>
        <div className="fields-2">
          <Field label="Role" htmlFor="u-role"><select id="u-role" className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as User["role"] })}>{Object.entries(meta?.roles ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Department" htmlFor="u-dept"><select id="u-dept" className="select" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>{meta?.departments.map((d) => <option key={d}>{d}</option>)}</select></Field>
        </div>
        <Field label={user ? "Reset the password (optional)" : "Password"} hint="At least 10 characters, with letters and digits." htmlFor="u-pass"><input id="u-pass" className="input" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required={!user} /></Field>
        {user && <label className="check"><input type="checkbox" checked={form.is_active} disabled={isSelf} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Account is active</label>}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
