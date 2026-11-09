import { Link } from "react-router-dom";
import { PageHeader, Panel } from "../components/ui";
import { GLOSSARY } from "../lib/glossary";
import { useMeta } from "../lib/queries";

const WORK = [
  { task: "Administer applications and support their users", where: "Applications, access lists, Support tickets, Users", to: "/support" },
  { task: "Evaluate and coordinate updates with the departments", where: "Change control: impact assessment per department, approval, release", to: "/changes" },
  { task: "Configure and keep improving the applications", where: "Configuration baseline of each application, held under change control", to: "/applications/1?tab=config" },
  { task: "Write validation documents and test thoroughly", where: "Requirements and risk, test cases, execution with evidence, deviations, PDF report", to: "/applications/1" },
  { task: "Train the users", where: "Training sessions and the training matrix per application version", to: "/training" },
  { task: "Report from the database", where: "Eight SQL views, with the SQL shown, exportable as CSV", to: "/reports" },
];

const TOUR = [
  { text: "Sign in as Sophie Gruber (validation engineer). The dashboard shows every application and where it is in the lifecycle.", to: "/" },
  { text: "Open DocuControl. Version 3.3 is in validation. The release gate says in words what is still open.", to: "/applications/1" },
  { text: "Look at the executions. One test failed, and the failure opened a deviation by itself.", to: "/applications/1?tab=runs" },
  { text: "Open the change request that created version 3.3: departments gave their impact, QA signed.", to: "/changes/1" },
  { text: "Open the traceability matrix: every requirement against the tests that prove it.", to: "/applications/1?tab=trace" },
  { text: "Switch to Eva Mayr (QA manager) to review runs, close the deviation with a signature and release.", to: "/deviations" },
  { text: "Open the audit trail and press Verify integrity. Then open SQL reports and press Show SQL.", to: "/audit" },
];

const IDEAS = [
  ["Risk-based validation (GAMP 5, ISO 13485 4.1.6)", "The GAMP category and a risk rating per requirement decide which tests are needed. The release gate checks them."],
  ["Traceability", "Requirements link to test cases, and test cases link to the runs on a version. The matrix and the report show gaps."],
  ["Audit trail (Part 11, Annex 11)", "Append-only table with a hash chain. Triggers in the database block changes and deletes; one SQL function re-checks the chain."],
  ["Electronic signatures (Part 11)", "Password typed again. The record stores name, role, meaning, time and the hash of what was signed."],
  ["Access control and segregation of duties", "Roles with fixed permissions. The author cannot approve, the executor cannot review, the requester cannot approve a change."],
  ["Change control (Annex 11)", "Request, impact assessment, approval, testing, release. Configuration of a validated system needs an approved change."],
  ["Data integrity (ALCOA+)", "Evidence is stored with its SHA-256. Times are set by the server. Records are attributable to a named person."],
  ["Training records", "Each person is trained on a specific version. A release asks for retraining of everybody who knew the old version."],
];

export default function About() {
  const { data: meta } = useMeta();
  return (
    <>
      <PageHeader
        eyebrow="Help"
        title="About ValiTrack"
        subtitle="A small system that does what a software quality engineer does every day: keep business applications validated while they change."
      />

      <div className="stack-lg">
        <Panel title="What is this?">
          <p>
            Companies that make medical devices must prove that the software they use for quality-relevant work does what it should, and keep proving it after every update.
            That proof is a set of documents: requirements, risk assessment, tests with results, a report, signatures.
            ValiTrack keeps those documents in one place, links them to each other and refuses to let a version go live while something is missing.
          </p>
          <p style={{ marginBottom: 0 }}>
            The data in this demo is invented. ValiTrack follows the main ideas of 21 CFR Part 11, EU GMP Annex 11 and GAMP 5, but it is a demonstration, not a validated product.
          </p>
        </Panel>

        <div className="grid-eq">
          <Panel title="The daily work, and where to find it" flush>
            <table className="table">
              <tbody>
                {WORK.map((w) => (
                  <tr key={w.task}>
                    <td><div className="title">{w.task}</div><div className="sub">{w.where}</div></td>
                    <td><Link to={w.to}>Open</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="A three-minute tour">
            <ol style={{ margin: 0, paddingLeft: 20 }}>
              {TOUR.map((t) => (
                <li key={t.text} style={{ marginBottom: 8 }}>{t.text} <Link to={t.to}>Go</Link></li>
              ))}
            </ol>
          </Panel>
        </div>

        <Panel title="Regulatory ideas and how they appear here" flush>
          <table className="table">
            <thead><tr><th>Idea</th><th>In ValiTrack</th></tr></thead>
            <tbody>{IDEAS.map(([a, b]) => <tr key={a}><td className="title">{a}</td><td>{b}</td></tr>)}</tbody>
          </table>
        </Panel>

        {meta && (
          <Panel title="Who may do what" flush>
            <div className="scroll-x">
              <table className="table">
                <thead>
                  <tr><th>Permission</th>{Object.entries(meta.roles).map(([key, label]) => <th key={key}>{label}</th>)}</tr>
                </thead>
                <tbody>
                  {Object.entries(meta.permission_labels).map(([perm, label]) => (
                    <tr key={perm}>
                      <td>{label}</td>
                      {Object.keys(meta.roles).map((role) => <td key={role} style={{ textAlign: "center" }}>{meta.role_permissions[role]?.includes(perm) ? <span aria-label="Allowed">●</span> : <span className="muted" aria-label="Not allowed">–</span>}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}

        <Panel title="Glossary">
          <dl className="kv" style={{ gridTemplateColumns: "minmax(140px, max-content) 1fr", gap: "12px 22px" }}>
            {Object.values(GLOSSARY).map((g) => (
              <div key={g.name} style={{ display: "contents" }}><dt style={{ fontWeight: 650, color: "var(--ink)" }}>{g.name}</dt><dd>{g.text}</dd></div>
            ))}
          </dl>
        </Panel>

        <Panel title="Limits">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>It is a demo. ValiTrack itself has not been validated, and a real installation would need its own validation.</li>
            <li>Production hardening that is described in the documentation but not built here: a database role without update and delete rights, an external time source, backups with restore tests, single sign-on.</li>
            <li>The hash chain shows that an entry was changed or removed in the middle. Removing the newest entries can only be detected by comparing the latest hash with one stored elsewhere.</li>
          </ul>
        </Panel>
      </div>
    </>
  );
}
