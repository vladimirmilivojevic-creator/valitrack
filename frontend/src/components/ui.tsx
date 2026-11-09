import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  CircleDot,
  Info,
  Loader2,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../lib/api";
import { GLOSSARY } from "../lib/glossary";
import { RISK, STATUS, type Tone } from "../lib/status";

const TONE_ICON: Record<Tone, typeof Circle> = {
  pass: CheckCircle2,
  fail: XCircle,
  warn: AlertTriangle,
  info: CircleDot,
  accent: CircleDot,
  neutral: Circle,
};

export function Chip({ tone = "neutral", children, outline }: { tone?: Tone; children: ReactNode; outline?: boolean }) {
  const Icon = TONE_ICON[tone];
  return (
    <span className={`chip chip--${tone} ${outline ? "chip--outline" : ""}`}>
      <Icon size={13} aria-hidden="true" />
      {children}
    </span>
  );
}

/** A status with an icon and a word, so colour is never the only signal. */
export function StatusChip({ status, label }: { status: string | null | undefined; label?: string }) {
  if (!status) return <span className="muted">-</span>;
  const entry = STATUS[status] ?? { label: status.replace(/_/g, " "), tone: "neutral" as Tone };
  return <Chip tone={entry.tone}>{label ?? entry.label}</Chip>;
}

export function RiskChip({ level }: { level: string | null | undefined }) {
  if (!level) return <span className="muted">not rated</span>;
  const entry = RISK[level];
  return <Chip tone={entry.tone}>{entry.label}</Chip>;
}

export const Id = ({ children }: { children: ReactNode }) => <span className="id">{children}</span>;

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="empty" role="status">
      <Loader2 size={20} className="spin" aria-hidden="true" /> {label}...
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <div className="banner banner--fail" role="alert">
      <XCircle size={18} aria-hidden="true" />
      <p>{errorMessage(error)}</p>
    </div>
  );
}

export function Banner({ tone = "info", children }: { tone?: "info" | "warn" | "fail" | "pass"; children: ReactNode }) {
  const Icon = tone === "fail" ? XCircle : tone === "warn" ? AlertTriangle : tone === "pass" ? CheckCircle2 : Info;
  return (
    <div className={`banner banner--${tone}`}>
      <Icon size={18} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  crumbs,
}: {
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  crumbs?: { to: string; label: string }[];
}) {
  return (
    <header className="page__head">
      <div>
        {crumbs && (
          <nav className="crumbs" aria-label="Breadcrumb">
            {crumbs.map((c) => (
              <span key={c.to}>
                <Link to={c.to}>{c.label}</Link> /{" "}
              </span>
            ))}
          </nav>
        )}
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export function Panel({
  title,
  actions,
  children,
  flush,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}) {
  return (
    <section className="panel">
      {(title || actions) && (
        <div className="panel__head">
          {typeof title === "string" ? <h2>{title}</h2> : <div className="grow">{title}</div>}
          {actions}
        </div>
      )}
      <div className={`panel__body ${flush ? "panel__body--flush" : ""}`}>{children}</div>
    </section>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal__backdrop">
      <div className={`modal ${wide ? "modal--wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal__head">
          <h2>{title}</h2>
          <button className="btn btn--ghost btn--icon" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="modal__body">{children}</div>
        {footer && <div className="modal__foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children?: ReactNode }) {
  const entry = GLOSSARY[k];
  if (!entry) return <>{children ?? k}</>;
  return (
    <span className="term" tabIndex={0} data-tip={`${entry.name}: ${entry.text}`}>
      {children ?? k}
    </span>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { key: T; label: string; count?: number }[];
  value: T;
  onChange: (key: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          role="tab"
          className="tab"
          aria-selected={tab.key === value}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
          {tab.count !== undefined && <span className="count">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}
