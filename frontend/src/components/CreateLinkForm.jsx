import { useState } from "react";
import { api } from "../api.js";

// <input type="datetime-local"> wants "YYYY-MM-DDTHH:mm" in the visitor's LOCAL time.
function localInputValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function CreateLinkForm({ onCreated }) {
  const [url, setUrl] = useState("");
  const [alias, setAlias] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const created = await api.create({
        url: url.trim(),
        alias: alias.trim(),
        // new Date("2026-10-22T14:30") is read as local time; toISOString converts it to UTC,
        // which is what the API stores and compares against.
        expiresAt: expiresAt ? new Date(expiresAt).toISOString() : null,
      });
      setUrl("");
      setAlias("");
      setExpiresAt("");
      setNotice(`Created ${created.short_url}`);
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="url">Long URL</label>
      <input id="url" type="url" required placeholder="https://example.com/a/very/long/address"
             value={url} onChange={(e) => setUrl(e.target.value)} />

      <div className="form-row">
        <div>
          <label htmlFor="alias">Custom alias (optional)</label>
          <input id="alias" type="text" placeholder="my-link" maxLength={32}
                 value={alias} onChange={(e) => setAlias(e.target.value)} />
          <p className="hint">3–32 characters: letters, digits, - or _</p>
        </div>
        <div>
          <label htmlFor="expires">Expires (optional)</label>
          <input id="expires" type="datetime-local" min={localInputValue(new Date())}
                 value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
          <p className="hint">After this time the link stops working.</p>
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? "Creating…" : "Shorten"}
      </button>
    </form>
  );
}