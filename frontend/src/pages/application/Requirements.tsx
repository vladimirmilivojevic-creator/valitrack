import { useQuery } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Empty, Field, Id, Loading, Modal, Panel, RiskChip, Term } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { riskOf } from "../../lib/format";
import { useMeta } from "../../lib/queries";
import { useAct } from "../../lib/toast";
import type { Application, Requirement } from "../../lib/types";

export default function Requirements({ app }: { app: Application }) {
  const { can } = useAuth();
  const { data: meta } = useMeta();
  const [editing, setEditing] = useState<Requirement | "new" | null>(null);
  const [retiring, setRetiring] = useState<Requirement | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["requirements", app.id],
    queryFn: () => api.get<Requirement[]>(`/applications/${app.id}/requirements`),
  });
  const items = data ?? [];
  const unrated = items.filter((r) => r.risk_level === null).length;

  return (
    <div className="stack-lg">
      <Panel
        title={`Requirements and risk assessment (${items.length})`}
        flush
        actions={
          can("req.write") && (
            <button className="btn btn--sm" onClick={() => setEditing("new")}>
              <Plus size={14} aria-hidden="true" /> Add requirement
            </button>
          )
        }
      >
        {isLoading ? (
          <Loading />
        ) : items.length === 0 ? (
          <Empty title="No requirements yet">Write down what the users need. Each requirement gets a risk rating and later a test.</Empty>
        ) : (
          <div className="scroll-x">
            <table className="table">
              <thead>
                <tr>
                  <th><Term k="URS">ID</Term></th>
                  <th>Requirement</th>
                  <th title="Severity / probability / detectability">S / P / D</th>
                  <th className="num"><Term k="RPN">RPN</Term></th>
                  <th>Risk</th>
                  <th>Tests</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id}>
                    <td><Id>{r.code}</Id></td>
                    <td style={{ paddingLeft: r.kind === "FS" ? 34 : undefined }}>
                      <div className="title">{r.title}</div>
                      <div className="sub">{r.description}</div>
                    </td>
                    <td className="mono nowrap">{r.severity ? `${r.severity} / ${r.probability} / ${r.detectability}` : "-"}</td>
                    <td className="num">{r.rpn ?? "-"}</td>
                    <td><RiskChip level={r.risk_level} /></td>
                    <td>{r.test_codes.length ? r.test_codes.map((c) => <Id key={c}>{c} </Id>) : <span className="muted">none</span>}</td>
                    <td className="nowrap">
                      {can("req.write") && (
                        <>
                          <button className="btn btn--sm btn--ghost" onClick={() => setEditing(r)} aria-label={`Edit ${r.code}`}>
                            <Pencil size={14} />
                          </button>
                          <button className="btn btn--sm btn--ghost" onClick={() => setRetiring(r)}>Retire</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {unrated > 0 && <p className="small muted">{unrated} requirements still need a risk rating. The requirements cannot be approved before that.</p>}

      {meta && (
        <Panel title="How the risk is rated">
          <p>
            Each requirement gets three ratings from 1 to 3: <strong>severity</strong> (how bad is a failure),{" "}
            <strong>probability</strong> (how likely) and <strong>detectability</strong> (how hard to notice). They are multiplied to the <Term k="RPN">RPN</Term>.
          </p>
          <p className="small muted" style={{ marginBottom: 0 }}>
            RPN {meta.risk.high_from} or more is high risk, {meta.risk.medium_from} to {meta.risk.high_from - 1} medium, below {meta.risk.medium_from} low.
            High and medium risk requirements need a scripted test, and QA reviews the tests of high-risk requirements.
          </p>
        </Panel>
      )}

      {editing && <RequirementDialog app={app} requirement={editing === "new" ? null : editing} items={items} onClose={() => setEditing(null)} />}
      {retiring && <RetireDialog requirement={retiring} onClose={() => setRetiring(null)} />}
    </div>
  );
}

function RatingSelect({ id, label, value, options, onChange }: { id: string; label: string; value: number | null; options: Record<string, string>; onChange: (v: number | null) => void }) {
  return (
    <Field label={label} htmlFor={id}>
      <select id={id} className="select" value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">Not rated</option>
        {Object.entries(options).map(([key, text]) => (
          <option key={key} value={key}>{key} - {text}</option>
        ))}
      </select>
    </Field>
  );
}

function RequirementDialog({ app, requirement, items, onClose }: { app: Application; requirement: Requirement | null; items: Requirement[]; onClose: () => void }) {
  const act = useAct();
  const { data: meta } = useMeta();
  const [form, setForm] = useState({
    kind: requirement?.kind ?? "URS",
    parent_id: requirement?.parent_id ?? (null as number | null),
    title: requirement?.title ?? "",
    description: requirement?.description ?? "",
    severity: requirement?.severity ?? (null as number | null),
    probability: requirement?.probability ?? (null as number | null),
    detectability: requirement?.detectability ?? (null as number | null),
    reason: "",
  });
  const [error, setError] = useState<string | null>(null);
  const risk = riskOf(form.severity, form.probability, form.detectability, meta?.risk.high_from, meta?.risk.medium_from);
  const parents = items.filter((r) => r.kind === "URS");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (requirement) {
        const { title, description, severity, probability, detectability, reason } = form;
        await act(() => api.patch(`/requirements/${requirement.id}`, { title, description, severity, probability, detectability, reason }), "Requirement saved.");
      } else {
        const { reason: _reason, ...body } = form;
        await act(() => api.post(`/applications/${app.id}/requirements`, body), "Requirement added.");
      }
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal
      title={requirement ? `Edit ${requirement.code}` : "New requirement"}
      wide
      onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--primary" type="submit" form="req-form">Save</button></>}
    >
      <form id="req-form" onSubmit={submit}>
        {!requirement && (
          <div className="fields-2">
            <Field label="Kind" htmlFor="r-kind">
              <select id="r-kind" className="select" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as "URS" | "FS" })}>
                <option value="URS">URS: what the users need</option>
                <option value="FS">FS: how the system does it</option>
              </select>
            </Field>
            {form.kind === "FS" && (
              <Field label="Belongs to requirement" htmlFor="r-parent">
                <select id="r-parent" className="select" value={form.parent_id ?? ""} onChange={(e) => setForm({ ...form, parent_id: Number(e.target.value) })} required>
                  <option value="">Choose</option>
                  {parents.map((p) => <option key={p.id} value={p.id}>{p.code} {p.title}</option>)}
                </select>
              </Field>
            )}
          </div>
        )}
        <Field label="Title" htmlFor="r-title"><input id="r-title" className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required autoFocus /></Field>
        <Field label="Description" hint="Write it so that a test can prove it." htmlFor="r-desc"><textarea id="r-desc" className="textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></Field>
        {meta && (
          <>
            <div className="fields-3">
              <RatingSelect id="r-sev" label="Severity" value={form.severity} options={meta.risk.severity} onChange={(v) => setForm({ ...form, severity: v })} />
              <RatingSelect id="r-prob" label="Probability" value={form.probability} options={meta.risk.probability} onChange={(v) => setForm({ ...form, probability: v })} />
              <RatingSelect id="r-det" label="Detectability" value={form.detectability} options={meta.risk.detectability} onChange={(v) => setForm({ ...form, detectability: v })} />
            </div>
            <p className="small">
              {risk ? <>RPN <strong>{risk.rpn}</strong> <RiskChip level={risk.level} /></> : <span className="muted">Rate all three to see the risk level.</span>}
            </p>
          </>
        )}
        {requirement && (
          <Field label="Reason for the change" hint="Goes into the audit trail." htmlFor="r-reason">
            <input id="r-reason" className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required />
          </Field>
        )}
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}

function RetireDialog({ requirement, onClose }: { requirement: Requirement; onClose: () => void }) {
  const act = useAct();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await act(() => api.post(`/requirements/${requirement.id}/retire`, { reason }), "Requirement retired.");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  return (
    <Modal title={`Retire ${requirement.code}`} onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn--danger" type="submit" form="retire-form">Retire</button></>}>
      <form id="retire-form" onSubmit={submit}>
        <p>{requirement.title}</p>
        <Field label="Reason" hint="A retired requirement no longer needs a test. The reason goes into the audit trail." htmlFor="ret-reason">
          <input id="ret-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus />
        </Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
