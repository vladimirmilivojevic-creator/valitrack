import { PenLine } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { errorMessage } from "../lib/api";
import { fmtDateTime, shortHash, utcLabel } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useMeta } from "../lib/queries";
import type { Signature } from "../lib/types";
import { Field, Modal } from "./ui";

interface SignatureModalProps {
  title: string;
  record: string;
  meaning: string;
  summary?: ReactNode;
  commentLabel?: string;
  commentRequired?: boolean;
  confirmLabel?: string;
  onSign: (password: string, comment: string) => Promise<unknown>;
  onClose: () => void;
}

/**
 * The electronic signature dialog. Like 21 CFR Part 11 asks, the signer types the password again,
 * and the dialog shows who signs, what the signature means and which record it covers.
 */
export function SignatureModal({
  title,
  record,
  meaning,
  summary,
  commentLabel = "Comment",
  commentRequired,
  confirmLabel = "Sign",
  onSign,
  onClose,
}: SignatureModalProps) {
  const { user } = useAuth();
  const { data: meta } = useMeta();
  const [password, setPassword] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSign(password, comment);
      onClose();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="sign-form" className="btn btn--primary" disabled={busy || !password}>
            <PenLine size={16} aria-hidden="true" /> {confirmLabel}
          </button>
        </>
      }
    >
      <form id="sign-form" onSubmit={submit}>
        <div className="sign-box">
          <div className="meaning">{meaning}</div>
          <div>{record}</div>
          <div className="muted small">
            Signing as {user?.full_name} ({meta?.roles[user?.role ?? ""] ?? user?.role}) at{" "}
            {utcLabel(new Date().toISOString())}
          </div>
        </div>
        {summary}
        <Field label={commentLabel + (commentRequired ? "" : " (optional)")} htmlFor="sign-comment">
          <textarea
            id="sign-comment"
            className="textarea"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            required={commentRequired}
          />
        </Field>
        <Field label="Password" hint="Type your password again to sign. This is your electronic signature." htmlFor="sign-password">
          <input
            id="sign-password"
            className="input"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {error && (
          <p role="alert" style={{ color: "var(--fail)", fontWeight: 600 }}>
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}

/** How a signature is shown on a record: name, role, meaning and time are always visible. */
export function SignatureList({ signatures, empty }: { signatures: Signature[]; empty?: string }) {
  const { data: meta } = useMeta();
  if (signatures.length === 0) return <p className="muted small">{empty ?? "No signatures yet."}</p>;
  return (
    <div>
      {signatures.map((s) => (
        <div className="sig" key={s.id}>
          <div>
            <span className="meaning">{s.meaning}</span>
            <strong>{s.signer_name}</strong> <span className="muted">({meta?.roles[s.signer_role] ?? s.signer_role})</span>
          </div>
          <div className="muted small" title={utcLabel(s.signed_at)}>
            {fmtDateTime(s.signed_at)} · {s.entity_label}
          </div>
          {s.comment && <div className="small">“{s.comment}”</div>}
          <div className="hash" title={`Signature hash ${s.signature_hash}\nRecord hash ${s.record_hash}`}>
            hash {shortHash(s.signature_hash, 16)}
          </div>
        </div>
      ))}
    </div>
  );
}
