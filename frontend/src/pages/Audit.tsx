import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck, ShieldAlert } from "lucide-react";
import { Fragment, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Banner, Empty, ErrorNote, Loading, PageHeader, Panel, Term } from "../components/ui";
import { api, qs } from "../lib/api";
import { fmtDateTime, shortHash, titleCase, utcLabel } from "../lib/format";
import type { AuditEntry } from "../lib/types";

const PAGE = 50;

interface Verify { entries: number; first_broken_seq: number | null; head_hash: string | null; intact: boolean }

export default function Audit() {
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useState({
    entity_type: params.get("entity_type") ?? "", entity_id: params.get("entity_id") ?? "", actor: "", action: "", q: params.get("q") ?? "", date_from: "", date_to: "",
  });
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<number | null>(null);
  const [verify, setVerify] = useState<Verify | null>(null);
  const [verifying, setVerifying] = useState(false);

  const query = qs({ ...filters, limit: PAGE, offset });
  const { data, error, isLoading } = useQuery({ queryKey: ["audit", query], queryFn: () => api.get<{ total: number; items: AuditEntry[] }>(`/audit${query}`) });

  async function runVerify() {
    setVerifying(true);
    try {
      setVerify(await api.get<Verify>("/audit/verify"));
    } finally {
      setVerifying(false);
    }
  }
  const set = (key: keyof typeof filters, value: string) => { setFilters({ ...filters, [key]: value }); setOffset(0); setParams({}, { replace: true }); };

  return (
    <>
      <PageHeader
        eyebrow="Insight"
        title="Audit trail"
        subtitle={<>Who did what and when. Entries can only be added: the database blocks changes and deletes, and every entry carries the hash of the one before it. See <Term k="Audit trail">how it works</Term>.</>}
        actions={
          <>
            <button className="btn btn--primary" onClick={() => void runVerify()} disabled={verifying}><ShieldCheck size={16} aria-hidden="true" /> {verifying ? "Checking" : "Verify integrity"}</button>
            <a className="btn" href={`/api/audit/export.csv${qs(filters)}`}><Download size={15} aria-hidden="true" /> CSV</a>
          </>
        }
      />

      {verify && (
        verify.intact ? (
          <Banner tone="pass"><p><strong>The chain is intact.</strong> {verify.entries} entries were recalculated and every hash matches. Latest hash: <span className="mono">{shortHash(verify.head_hash, 16)}</span></p></Banner>
        ) : (
          <Banner tone="fail"><p><ShieldAlert size={16} aria-hidden="true" /> <strong>The chain is broken at entry {verify.first_broken_seq}.</strong> That entry, or one before it, was changed or removed outside the application.</p></Banner>
        )
      )}

      <div className="panel" style={{ padding: 14, marginBottom: 16 }}>
        <div className="fields-3" style={{ marginBottom: -6 }}>
          <div className="field"><label htmlFor="f-type">Record type</label><input id="f-type" className="input" placeholder="e.g. change_request" value={filters.entity_type} onChange={(e) => set("entity_type", e.target.value)} /></div>
          <div className="field"><label htmlFor="f-q">Record name contains</label><input id="f-q" className="input" placeholder="e.g. CR-0001" value={filters.q} onChange={(e) => set("q", e.target.value)} /></div>
          <div className="field"><label htmlFor="f-actor">Person</label><input id="f-actor" className="input" value={filters.actor} onChange={(e) => set("actor", e.target.value)} /></div>
          <div className="field"><label htmlFor="f-action">Action</label><input id="f-action" className="input" placeholder="e.g. sign" value={filters.action} onChange={(e) => set("action", e.target.value)} /></div>
          <div className="field"><label htmlFor="f-from">From</label><input id="f-from" className="input" type="date" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} /></div>
          <div className="field"><label htmlFor="f-to">To</label><input id="f-to" className="input" type="date" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} /></div>
        </div>
      </div>

      <Panel flush>
        {isLoading ? <Loading /> : error ? <ErrorNote error={error} /> : (data?.items ?? []).length === 0 ? <Empty title="No entries match" /> : (
          <div className="scroll-x">
            <table className="table">
              <thead><tr><th>#</th><th>When</th><th>Who</th><th>Action</th><th>Record</th><th>Reason</th></tr></thead>
              <tbody>
                {data!.items.map((e) => (
                  <Fragment key={e.seq}>
                    <tr onClick={() => setOpen(open === e.seq ? null : e.seq)} style={{ cursor: "pointer" }}>
                      <td className="id">{e.seq}</td>
                      <td className="nowrap" title={utcLabel(e.occurred_at)}>{fmtDateTime(e.occurred_at)}</td>
                      <td>{e.actor_name}</td>
                      <td><strong>{titleCase(e.action)}</strong></td>
                      <td>{e.entity_label ?? e.entity_id}<div className="sub">{e.entity_type} {e.entity_id}</div></td>
                      <td>{e.reason}</td>
                    </tr>
                    {open === e.seq && (
                      <tr>
                        <td />
                        <td colSpan={5}>
                          <div className="grid-eq" style={{ gap: 14 }}>
                            <div><div className="eyebrow">Before</div><pre className="sql">{e.old_values ? JSON.stringify(e.old_values, null, 2) : "(nothing)"}</pre></div>
                            <div><div className="eyebrow">After</div><pre className="sql">{e.new_values ? JSON.stringify(e.new_values, null, 2) : "(nothing)"}</pre></div>
                          </div>
                          <p className="hash" style={{ marginTop: 8 }}>previous hash {e.prev_hash}<br />entry hash {e.entry_hash}</p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {data && data.total > PAGE && (
        <div className="row" style={{ marginTop: 14, justifyContent: "space-between" }}>
          <span className="small muted">Showing {offset + 1} to {Math.min(offset + PAGE, data.total)} of {data.total}</span>
          <div className="row">
            <button className="btn btn--sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Newer</button>
            <button className="btn btn--sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Older</button>
          </div>
        </div>
      )}
    </>
  );
}
