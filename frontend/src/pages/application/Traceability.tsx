import { useQuery } from "@tanstack/react-query";
import { Check, Minus, X } from "lucide-react";
import { Link } from "react-router-dom";
import { Empty, Id, Loading, Panel, Term } from "../../components/ui";
import { api } from "../../lib/api";
import type { Application, Requirement, Run, TestCase } from "../../lib/types";

/** Requirements down the side, tests across the top. A gap means a requirement nobody proves. */
export default function Traceability({ app }: { app: Application }) {
  const version = app.working_version ?? app.live_version;
  const reqs = useQuery({ queryKey: ["requirements", app.id], queryFn: () => api.get<Requirement[]>(`/applications/${app.id}/requirements`) });
  const tests = useQuery({ queryKey: ["tests", app.id], queryFn: () => api.get<TestCase[]>(`/applications/${app.id}/test-cases`) });
  const runs = useQuery({
    queryKey: ["runs", "version", version?.id],
    enabled: !!version,
    queryFn: () => api.get<Run[]>(`/runs?version_id=${version!.id}`),
  });

  if (reqs.isLoading || tests.isLoading) return <Loading />;
  const requirements = reqs.data ?? [];
  const cases = (tests.data ?? []).filter((t) => t.status !== "retired");
  if (requirements.length === 0 || cases.length === 0) {
    return <Empty title="Nothing to trace yet">Add requirements and test cases first. This matrix links them.</Empty>;
  }

  const latest = new Map<number, Run>();
  for (const run of runs.data ?? []) if (run.status === "completed" && !latest.has(run.test_case_id)) latest.set(run.test_case_id, run);
  const covered = requirements.filter((r) => r.test_case_ids.some((id) => cases.some((c) => c.id === id && c.status === "approved"))).length;

  return (
    <div className="stack-lg">
      <Panel
        title={<span><Term k="Traceability">Traceability matrix</Term>{version ? <span className="muted" style={{ fontWeight: 500 }}> · results on version {version.version}</span> : null}</span>}
        actions={<span className="small muted">{covered} of {requirements.length} requirements covered by an approved test</span>}
        flush
      >
        <div className="scroll-x" style={{ padding: 16 }}>
          <table className="matrix">
            <thead>
              <tr>
                <th className="left">Requirement</th>
                {cases.map((t) => (
                  <th key={t.id} title={`${t.title} (${t.status})`}>
                    <Id>{t.code}</Id>
                    <div className="small muted">{t.test_type}{t.status !== "approved" ? " (draft)" : ""}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {requirements.map((r) => {
                const gap = !r.test_case_ids.some((id) => cases.some((c) => c.id === id && c.status === "approved"));
                return (
                  <tr key={r.id}>
                    <td className={`left ${gap ? "gap" : ""}`} style={{ paddingLeft: r.kind === "FS" ? 26 : undefined }}>
                      <Id>{r.code}</Id> {r.title}
                      {gap && <div className="small" style={{ color: "var(--warn)", fontWeight: 600 }}>No approved test covers this</div>}
                    </td>
                    {cases.map((t) => {
                      if (!r.test_case_ids.includes(t.id)) return <td key={t.id} className="cell none"><Minus size={14} aria-label="Not linked" /></td>;
                      const run = latest.get(t.id);
                      if (!run) return <td key={t.id} className="cell none" title="Linked, not executed on this version">o</td>;
                      return run.result === "passed" ? (
                        <td key={t.id} className="cell pass"><Link to={`/runs/${run.id}`} aria-label={`${t.code} passed`}><Check size={16} /></Link></td>
                      ) : (
                        <td key={t.id} className="cell fail"><Link to={`/runs/${run.id}`} aria-label={`${t.code} ${run.result}`}><X size={16} /></Link></td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="small muted" style={{ padding: "0 16px 14px", margin: 0 }}>
          <Check size={13} aria-hidden="true" /> passed &nbsp; <X size={13} aria-hidden="true" /> failed or blocked &nbsp; o linked, not executed &nbsp; <Minus size={13} aria-hidden="true" /> not linked. Hatched rows have no approved test.
        </p>
      </Panel>
    </div>
  );
}
