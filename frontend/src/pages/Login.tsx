import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { LogoMark } from "../components/Shell";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { DemoAccounts } from "../lib/types";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const demo = useQuery({ queryKey: ["demo-accounts"], queryFn: () => api.get<DemoAccounts>("/demo/accounts") });

  if (user) return <Navigate to="/" replace />;

  async function signIn(name: string, secret: string) {
    setBusy(true);
    setError(null);
    try {
      await login(name, secret);
      navigate("/", { replace: true });
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void signIn(username, password);
  };

  return (
    <div className="login">
      <section className="login__intro">
        <div className="row" style={{ gap: 12 }}>
          <LogoMark size={34} />
          <strong style={{ fontSize: 20 }}>ValiTrack</strong>
        </div>
        <div>
          <h1>Prove that your software does what it should.</h1>
          <div className="rule" />
          <p>
            Validation of business applications, change control with electronic signatures, and an audit trail that
            nobody can edit. Built around the daily work of a software quality engineer in a regulated company.
          </p>
        </div>
        <p className="small" style={{ margin: 0, display: "flex", gap: 8, alignItems: "center" }}>
          <ShieldCheck size={16} aria-hidden="true" /> Demo with invented data. Not validated for real GxP use.
        </p>
      </section>

      <section className="login__form">
        <h2 style={{ fontSize: 24, marginBottom: 6 }}>Sign in</h2>
        <p className="muted">Use your account, or pick one of the demo roles below.</p>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="username">User name</label>
            <input id="username" className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          {error && (
            <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>
              {error}
            </p>
          )}
          <button className="btn btn--primary" type="submit" disabled={busy || !username || !password}>
            Sign in
          </button>
        </form>

        {demo.data?.enabled && (
          <div style={{ marginTop: 28 }}>
            <div className="eyebrow">Demo accounts. Click one to sign in.</div>
            <ul className="demo-list">
              {demo.data.accounts.map((account) => (
                <li key={account.username}>
                  <button disabled={busy} onClick={() => void signIn(account.username, demo.data?.password ?? "")}>
                    <b>
                      {account.full_name} <span className="muted" style={{ fontWeight: 500 }}>· {account.role_label}</span>
                    </b>
                    <span className="muted small">{account.hint}</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="small muted" style={{ marginTop: 10 }}>
              All demo accounts share the password <code>{demo.data.password}</code>. Signatures ask for it again.
              The data is reset every night.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
