import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Empty, ErrorNote, Loading, PageHeader, Panel } from "../components/ui";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { ReportData, ReportInfo } from "../lib/types";

const pretty = (column: string) => column.replace(/_/g, " ");

function Cell({ column, value }: { column: string; value: string | number | boolean | null }) {
  if (value === null) return <span className="muted">-</span>;
  if (column.endsWith("_pct")) {
    const pct = Math.max(0, Math.min(100, Number(value)));
    return (
      <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
        <div className="bar pass" style={{ width: 70 }}><span style={{ width: `${pct}%` }} /></div>
        <span className="small">{pct}%</span>
      </div>
    );
  }
  if (typeof value === "boolean") return <>{value ? "yes" : "no"}</>;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) return <>{fmtDateTime(value)}</>;
  if (typeof value === "string" && /^[a-z]+(_[a-z]+)+$/.test(value)) return <>{value.replace(/_/g, " ")}</>;
  return <>{String(value)}</>;
}

export default function Reports() {
  const [params, setParams] = useSearchParams();
  const catalog = useQuery({ queryKey: ["report-catalog"], queryFn: () => api.get<ReportInfo[]>("/reports"), staleTime: Infinity });
  const key = params.get("r") ?? catalog.data?.[0]?.key;
  const [showSql, setShowSql] = useState(false);
  const report = useQuery({ queryKey: ["report", key], enabled: !!key, queryFn: () => api.get<ReportData>(`/reports/${key}`) });

  return (
    <>
      <PageHeader
        eyebrow="Insight"
        title="SQL reports"
        subtitle="Every report is a view in the PostgreSQL database. You see the answer and the SQL behind it, and you can export it as CSV for Excel or Power BI."
      />
      <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 300px) minmax(0, 1fr)" }}>
        <Panel title="Questions" flush>
          {catalog.isLoading ? <Loading /> : (
            <nav aria-label="Reports">
              {(catalog.data ?? []).map((r) => (
                <button
                  key={r.key}
                  onClick={() => { setParams({ r: r.key }); setShowSql(false); }}
                  style={{ all: "unset", boxSizing: "border-box", display: "block", width: "100%", padding: "11px 16px", cursor: "pointer", borderBottom: "1px solid var(--rule)", borderLeft: `3px solid ${r.key === key ? "var(--accent)" : "transparent"}`, background: r.key === key ? "var(--sunken)" : undefined }}
                  aria-current={r.key === key ? "true" : undefined}
                >
                  <strong style={{ display: "block" }}>{r.title}</strong>
                  <span className="small muted">{r.question}</span>
                </button>
              ))}
            </nav>
          )}
        </Panel>

        <div>
          {report.isLoading && <Loading />}
          {report.error && <ErrorNote error={report.error} />}
          {report.data && (
            <Panel
              title={<span>{report.data.title}<div className="muted small" style={{ fontWeight: 400 }}>{report.data.explain}</div></span>}
              flush
              actions={
                <>
                  <button className="btn btn--sm" onClick={() => setShowSql(!showSql)} aria-expanded={showSql}>{showSql ? "Hide SQL" : "Show SQL"}</button>
                  <a className="btn btn--sm" href={`/api/reports/${report.data.key}/csv`}><Download size={14} aria-hidden="true" /> CSV</a>
                </>
              }
            >
              {showSql && <div style={{ padding: 14 }}><pre className="sql">{report.data.sql}</pre></div>}
              {report.data.rows.length === 0 ? <Empty title="No rows">The view returns nothing right now.</Empty> : (
                <div className="scroll-x">
                  <table className="table">
                    <thead><tr>{report.data.columns.map((c) => <th key={c} className={report.data.rows.some((r) => typeof r[report.data.columns.indexOf(c)] === "number") ? "num" : undefined}>{pretty(c)}</th>)}</tr></thead>
                    <tbody>
                      {report.data.rows.map((row, i) => (
                        <tr key={i}>
                          {row.map((value, j) => (
                            <td key={j} className={typeof value === "number" ? "num" : undefined}><Cell column={report.data.columns[j]} value={value} /></td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="small muted" style={{ padding: "10px 16px 14px", margin: 0 }}>{report.data.rows.length} rows from view <code>{report.data.view}</code>.</p>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
