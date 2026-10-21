import { useEffect, useState } from "react";
import { api } from "../api.js";
import CreateLinkForm from "../components/CreateLinkForm.jsx";
import LinkRow from "../components/LinkRow.jsx";

const PAGE_SIZE = 50;

export default function Dashboard() {
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0); // bump it to fetch the first page again

  useEffect(() => {
    let cancelled = false; // ignore a response that arrives after the page was left or refreshed
    api.list(PAGE_SIZE, 0)
      .then((page) => {
        if (cancelled) return;
        setLinks(page);
        setHasMore(page.length === PAGE_SIZE); // a full page suggests there may be more
      })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reloadKey]);

  function refresh() {
    setLoading(true);
    setError("");
    setReloadKey((key) => key + 1);
  }

  async function loadMore() {
    setLoadingMore(true);
    try {
      const page = await api.list(PAGE_SIZE, links.length);
      setLinks((current) => {
        const seen = new Set(current.map((l) => l.short_code));
        return [...current, ...page.filter((l) => !seen.has(l.short_code))];
      });
      setHasMore(page.length === PAGE_SIZE);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingMore(false);
    }
  }

  // The create response has no click_count, and a new link has none yet.
  const handleCreated = (created) => setLinks((current) => [{ ...created, click_count: 0 }, ...current]);
  const handleDeleted = (code) => setLinks((current) => current.filter((l) => l.short_code !== code));

  return (
    <>
      <div className="card">
        <h1>Shorten a link</h1>
        <CreateLinkForm onCreated={handleCreated} />
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Your links</h2>
          <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>Refresh</button>
        </div>
        <p className="hint">Click counts update a few seconds after a visit.</p>

        {error && <p className="error" role="alert">{error}</p>}

        {loading ? (
          <p className="muted">Loading…</p>
        ) : links.length === 0 ? (
          <p className="muted">No links yet. Create your first one above.</p>
        ) : (
          <ul className="links">
            {links.map((link) => (
              <LinkRow key={link.short_code} link={link} onDeleted={handleDeleted} />
            ))}
          </ul>
        )}

        {hasMore && !loading && (
          <button className="btn btn-ghost more" onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        )}
      </div>
    </>
  );
}