import {
  AlertOctagon,
  BarChart3,
  BookOpen,
  Boxes,
  GitPullRequest,
  GraduationCap,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Menu,
  Moon,
  ScrollText,
  Sun,
  Users,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useMeta } from "../lib/queries";
import { useToast } from "../lib/toast";
import { Field, Modal } from "./ui";

export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="7" fill="var(--ink)" />
      <path d="M8 16.5l5.2 5.2L24 10.5" fill="none" stroke="var(--paper)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="24.5" cy="8" r="3.2" fill="var(--accent)" />
    </svg>
  );
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const saved = localStorage.getItem("vt-theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* storage is not available */
    }
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("vt-theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

const NAV = [
  { group: "Overview", items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }] },
  {
    group: "Validate",
    items: [
      { to: "/applications", label: "Applications", icon: Boxes },
      { to: "/deviations", label: "Deviations", icon: AlertOctagon },
    ],
  },
  { group: "Change", items: [{ to: "/changes", label: "Change control", icon: GitPullRequest }] },
  {
    group: "Operate",
    items: [
      { to: "/training", label: "Training", icon: GraduationCap },
      { to: "/support", label: "Support", icon: LifeBuoy },
    ],
  },
  {
    group: "Insight",
    items: [
      { to: "/reports", label: "SQL reports", icon: BarChart3 },
      { to: "/audit", label: "Audit trail", icon: ScrollText },
    ],
  },
];

export function Shell() {
  const { user, can, logout } = useAuth();
  const { data: meta } = useMeta();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="app">
      <div className="topbar">
        <button className="btn btn--ghost btn--icon" onClick={() => setOpen(true)} aria-label="Open the menu">
          <Menu size={20} />
        </button>
        <LogoMark size={26} />
        <strong>ValiTrack</strong>
      </div>

      <aside className={`rail ${open ? "open" : ""}`} aria-label="Main">
        <NavLink to="/" className="rail__brand">
          <LogoMark />
          <span>
            ValiTrack
            <small>Validation and change control</small>
          </span>
        </NavLink>
        <nav className="rail__nav">
          {NAV.map((section) => (
            <div key={section.group}>
              <div className="rail__group">{section.group}</div>
              {section.items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `rail__link ${isActive ? "active" : ""}`}>
                  <item.icon size={17} aria-hidden="true" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
          {can("user.manage") && (
            <div>
              <div className="rail__group">Administration</div>
              <NavLink to="/admin/users" className={({ isActive }) => `rail__link ${isActive ? "active" : ""}`}>
                <Users size={17} aria-hidden="true" /> Users
              </NavLink>
            </div>
          )}
          <div>
            <div className="rail__group">Help</div>
            <NavLink to="/about" className={({ isActive }) => `rail__link ${isActive ? "active" : ""}`}>
              <BookOpen size={17} aria-hidden="true" /> About and tour
            </NavLink>
          </div>
        </nav>
        <div className="rail__user">
          <strong>{user?.full_name}</strong>
          <span className="muted small">
            {meta?.roles[user?.role ?? ""] ?? user?.role} · {user?.department}
          </span>
          <div className="row">
            <button className="btn btn--sm btn--ghost btn--icon" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title="Switch theme">
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button className="btn btn--sm btn--ghost btn--icon" onClick={() => setChangingPassword(true)} aria-label="Change password" title="Change password">
              <KeyRound size={16} />
            </button>
            <button className="btn btn--sm" onClick={() => void logout()}>
              <LogOut size={15} aria-hidden="true" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="page">
          <Outlet />
        </div>
      </main>
      {changingPassword && <PasswordModal onClose={() => setChangingPassword(false)} />}
    </div>
  );
}

function PasswordModal({ onClose }: { onClose: () => void }) {
  const notify = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      notify("Password changed.");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal
      title="Change password"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn--primary" type="submit" form="password-form">
            Change password
          </button>
        </>
      }
    >
      <form id="password-form" onSubmit={submit}>
        <Field label="Current password" htmlFor="pw-current">
          <input id="pw-current" className="input" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
        </Field>
        <Field label="New password" hint="At least 10 characters, with letters and digits." htmlFor="pw-new">
          <input id="pw-new" className="input" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        {error && <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>{error}</p>}
      </form>
    </Modal>
  );
}
