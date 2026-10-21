import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Link } from "react-router-dom";

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function LinkRow({ link, onDeleted }) {
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const expired = link.expires_at && new Date(link.expires_at) <= new Date();

  // Reset the "Copied!" label after a moment. The cleanup stops the timer if the row unmounts.
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(link.short_url);
      setCopied(true);
    } catch {
      setError("Could not copy automatically. Select the link and copy it by hand.");
    }
  }

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api.remove(link.short_code);
      onDeleted(link.short_code); // the parent removes this row, so no state reset is needed here
    } catch (err) {
      setError(err.message);
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <li className="link">
      <div className="link-main">
        <a href={link.short_url} target="_blank" rel="noopener noreferrer" className="short-url">
          {link.short_url}
        </a>
        {/* Plain text on purpose: never put a user-supplied URL into an href. */}
        <span className="original" title={link.original_url}>{link.original_url}</span>
        <div className="meta">
          <span>{link.click_count} {link.click_count === 1 ? "click" : "clicks"}</span>
          <span>Created {formatDate(link.created_at)}</span>
          {link.expires_at &&
            (expired
              ? <span className="badge badge-expired">Expired</span>
              : <span className="badge">Expires {formatDate(link.expires_at)}</span>)}
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </div>

      <div className="link-actions">
        <Link className="btn btn-ghost btn-sm" to={`/links/${encodeURIComponent(link.short_code)}`}>Stats</Link>
        <button className="btn btn-ghost btn-sm" onClick={copy}>{copied ? "Copied!" : "Copy"}</button>
        {confirming ? (
          <>
            <button className="btn btn-danger btn-sm" onClick={remove} disabled={busy}>
              {busy ? "Deleting…" : "Confirm"}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setConfirming(false)} disabled={busy}>
              Cancel
            </button>
          </>
        ) : (
          <button className="btn btn-ghost btn-sm" onClick={() => setConfirming(true)}>Delete</button>
        )}
      </div>
    </li>
  );
}