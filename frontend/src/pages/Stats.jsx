import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import BarChart from "../components/BarChart.jsx";

const RANGES = [7, 30, 90]; // the API allows 1 to 90 days

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function RankList({ title, rows, nameKey }) {
  const max = Math.max(1, ...rows.map((r) => r.clicks));
  return (
    <div>
      <h2>{title}</h2>
      {rows.length === 0 ? (
        <p className="muted">No data yet.</p>
      ) : (
        <ul className="rank">
          {rows.map((row) => (
            <li key={row[nameKey]}>
              <span className="fill" style={{ width: `${(row.clicks / max) * 100}%` }} />
              {/* Text only: referrers are chosen by the visitor, never turn them into links. */}
              <span className="name" title={row[nameKey]}>{row[nameKey]}</span>
              <span>{row.clicks}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Stats() {
  const { code } = useParams();
  const [days, setDays] = useState(30);
  const [info, setInfo] = useState(null);       // lifetime numbers from /analytics
  const [summary, setSummary] = useState(null); // the chart data from /analytics/summary
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false; // ignore a response that arrives after a newer request was made
    Promise.all([api.analytics(code), api.summary(code, days)])
      .then(([analytics, sum]) => {
        if (cancelled) return;
        setInfo(analytics.stats);
        setSummary(sum);
      })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [code, days, reloadKey]);

  function changeRange(next) {
    if (next === days) return;
    setLoading(true);
    setError("");
    setDays(next);
  }

  function refresh() {
    setLoading(true);
    setError("");
    setReloadKey((key) => key + 1);
  }

  return (
    <>
      <Link to="/" className="back">← Your links</Link>

      {error && <div className="card"><p className="error" role="alert">{error}</p></div>}
      {!error && !info && <p className="muted">Loading…</p>}

      {info && summary && (
        <>
          <div className="card" aria-busy={loading}>
            <div className="card-header">
              <h1>/{info.short_code}</h1>
              <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>Refresh</button>
            </div>
            <p className="original-line">{info.original_url}</p>
            <dl className="facts">
              <div className="fact"><dt>Total clicks</dt><dd>{info.click_count}</dd></div>
              <div className="fact"><dt>Created</dt><dd>{formatDate(info.created_at)}</dd></div>
              <div className="fact">
                <dt>Last click</dt>
                <dd>{info.last_clicked_at ? formatDate(info.last_clicked_at) : "No clicks yet"}</dd>
              </div>
              {info.expires_at && (
                <div className="fact"><dt>Expires</dt><dd>{formatDate(info.expires_at)}</dd></div>
              )}
            </dl>
          </div>

          <div className="card" aria-busy={loading}>
            <div className="card-header">
              <h2>Clicks per day</h2>
              <div className="range" role="group" aria-label="Time range">
                {RANGES.map((r) => (
                  <button key={r} className="btn btn-ghost btn-sm" aria-pressed={days === r}
                          disabled={loading} onClick={() => changeRange(r)}>
                    {r} days
                  </button>
                ))}
              </div>
            </div>
            <p className="hint">
              {summary.total_clicks} {summary.total_clicks === 1 ? "click" : "clicks"} in the last {days} days.
              Days are in UTC, and counts can lag a few seconds behind real visits.
            </p>
            {summary.total_clicks === 0
              ? <p className="muted">No clicks in this period yet.</p>
              : <BarChart data={summary.clicks_per_day} />}
          </div>

          <div className="card split">
            <RankList title="Top referrers" rows={summary.top_referrers} nameKey="referrer" />
            <RankList title="Browsers" rows={summary.browsers} nameKey="browser" />
          </div>
        </>
      )}
    </>
  );
}