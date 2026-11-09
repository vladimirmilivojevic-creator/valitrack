import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { LifecycleStepper } from "../components/Gate";
import { Empty, ErrorNote, Loading, PageHeader, Panel, RiskChip, Term } from "../components/ui";
import { api } from "../lib/api";
import { fmtDateTime, titleCase } from "../lib/format";
import { useAuth } from "../lib/auth";
import type { Dashboard as DashboardData } from "../lib/types";

const WHAT: Record<string, string> = {
  sign: "signed",
  status_change: "moved",
  complete: "completed",
  review: "reviewed",
  validate: "validated",
  supersede: "superseded",
  approve_urs: "approved the requirements of",
  approve: "approved",
  close: "closed",
  accept: "accepted",
  resolve: "resolved",
  generate: "generated",
  assess: "assessed",
  plan_tests: "planned the tests of",
};

export default function Dashboard() {
  const { user } = useAuth();
  const { data, error, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<DashboardData>("/dashboard") });

  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorNote error={error} />;
  const a = data.attention;
  const stats = [
    { to: "/changes", value: a.open_changes, label: "Open changes", attention: a.changes_awaiting_approval > 0, note: `${a.changes_awaiting_approval} awaiting approval` },
    { to: "/deviations", value: a.open_deviations, label: "Open deviations", attention: a.open_deviations > 0 },
    { to: "/applications", value: a.runs_awaiting_review, label: "Runs to review", attention: a.runs_awaiting_review > 0 },
    { to: "/training", value: a.training_gaps, label: "Training gaps", attention: a.training_gaps > 0 },
    { to: "/support", value: a.open_tickets, label: "Open tickets" },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title={`Good to see you, ${user?.full_name.split(" ")[0]}`}
        subtitle="Where every application stands in its validation, and what needs a decision today."
      />

      <div className="stat-strip">
        {stats.map((s) => (
          <Link key={s.label} to={s.to} className={`stat ${s.attention ? "attention" : ""}`}>
            <div className="value">{s.value}</div>
            <div className="label">{s.label}</div>
            {s.note && <div className="label small">{s.note}</div>}
          </Link>
        ))}
      </div>

      <div className="stack-lg">
        <Panel title="Validation lifecycle" flush>
          {data.board.length === 0 ? (
            <Empty title="No applications yet" />
          ) : (
            <div className="scroll-x">
              <table className="table">
                <thead>
                  <tr>
                    <th>Application</th>
                    <th>
                      <Term k="GAMP">GAMP</Term>
                    </th>
                    <th>Risk</th>
                    <th>Live</th>
                    <th>In validation</th>
                    <th>Lifecycle</th>
                  </tr>
                </thead>
                <tbody>
                  {data.board.map((row) => (
                    <tr key={row.application_id}>
                      <td>
                        <Link className="title" to={`/applications/${row.application_id}`}>
                          {row.name}
                        </Link>
                        <div className="sub id">{row.code}</div>
                      </td>
                      <td>{row.gamp_category}</td>
                      <td>
                        <RiskChip level={row.risk_class} />
                      </td>
                      <td className="mono">{row.live_version ?? "-"}</td>
                      <td className="mono">{row.working_version ?? "-"}</td>
                      <td>
                        <LifecycleStepper stage={row.stage} />
                        {row.open_checks > 0 && (
                          <div className="sub">
                            {row.open_checks} gate {row.open_checks === 1 ? "check" : "checks"} open
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Recent activity" flush>
          <ul className="activity">
            {data.activity.slice(0, 8).map((e) => (
              <li key={e.seq}>
                <strong>{e.actor_name}</strong> {WHAT[e.action] ?? titleCase(e.action).toLowerCase()}{" "}
                <span className="id">{e.entity_label ?? e.entity_type}</span>
                <time>{fmtDateTime(e.occurred_at)}</time>
              </li>
            ))}
          </ul>
          <p className="small" style={{ padding: "8px 16px 14px", margin: 0 }}>
            <Link to="/audit">Open the full audit trail</Link>
          </p>
        </Panel>
      </div>
    </>
  );
}
