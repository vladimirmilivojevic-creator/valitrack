import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Empty, Id, Loading, Panel, StatusChip } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtDateTime } from "../../lib/format";
import { useUsers } from "../../lib/queries";
import type { Application, Run } from "../../lib/types";

export default function Executions({ app }: { app: Application }) {
  const { name } = useUsers();
  const { data, isLoading } = useQuery({ queryKey: ["runs", "application", app.id], queryFn: () => api.get<Run[]>(`/runs?application_id=${app.id}`) });
  if (isLoading) return <Loading />;
  const runs = data ?? [];
  return (
    <Panel title={`Test executions (${runs.length})`} flush>
      {runs.length === 0 ? (
        <Empty title="No test has been executed yet">Open the Tests tab and press Execute on an approved test case.</Empty>
      ) : (
        <div className="scroll-x">
          <table className="table table--hover">
            <thead><tr><th>Run</th><th>Test</th><th>Version</th><th>Result</th><th>Executed by</th><th>Completed</th><th>QA review</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td><Link to={`/runs/${r.id}`} className="id">RUN-{r.id}</Link></td>
                  <td><Id>{r.test_code}</Id> {r.test_title}</td>
                  <td className="mono">{r.version}</td>
                  <td><StatusChip status={r.status === "completed" ? r.result : "in_progress"} /></td>
                  <td>{name(r.executed_by)}</td>
                  <td>{fmtDateTime(r.completed_at)}</td>
                  <td>{r.reviewed_at ? <span>{name(r.reviewed_by)}</span> : r.status === "completed" ? <span className="muted">waiting</span> : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
