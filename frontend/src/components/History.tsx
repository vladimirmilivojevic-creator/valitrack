import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, qs } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { AuditEntry } from "../lib/types";
import { Empty, ErrorNote, Loading } from "./ui";

/** The audit trail of one record. */
export function History({ entityType, entityId }: { entityType: string; entityId: number }) {
  const { data, error, isLoading } = useQuery({
    queryKey: ["history", entityType, entityId],
    queryFn: () =>
      api.get<{ total: number; items: AuditEntry[] }>(`/audit${qs({ entity_type: entityType, entity_id: entityId, limit: 100 })}`),
  });
  if (isLoading) return <Loading />;
  if (error) return <ErrorNote error={error} />;
  const items = data?.items ?? [];
  if (items.length === 0) return <Empty title="No history yet" />;
  return (
    <div className="scroll-x">
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>When</th>
            <th>Who</th>
            <th>What</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => (
            <tr key={e.seq}>
              <td className="id">{e.seq}</td>
              <td className="nowrap">{fmtDateTime(e.occurred_at)}</td>
              <td>{e.actor_name}</td>
              <td>
                <strong>{e.action.replace(/_/g, " ")}</strong>
                {e.new_values && <div className="sub mono">{summarise(e.new_values)}</div>}
              </td>
              <td>{e.reason ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="small muted" style={{ padding: "8px 14px" }}>
        <Link to={`/audit?entity_type=${entityType}&entity_id=${entityId}`}>Open in the audit trail</Link>
      </p>
    </div>
  );
}

function summarise(values: Record<string, unknown>): string {
  const text = Object.entries(values)
    .filter(([, v]) => v !== null && typeof v !== "object")
    .slice(0, 4)
    .map(([k, v]) => `${k}: ${String(v).slice(0, 40)}`)
    .join(", ");
  return text;
}
