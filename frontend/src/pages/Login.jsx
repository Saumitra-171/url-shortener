import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault(); // stop the browser's own form submission
    setError("");
    setBusy(true);
    try {
      await login(email.trim(), password);
      // On success the guard sees the user and redirects, so there is nothing to do here.
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card auth-card">
      <h1>Log in</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="email" required
               value={email} onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" required
               value={password} onChange={(e) => setPassword(e.target.value)} />

        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="muted">No account? <Link to="/register">Create one</Link></p>
    </div>
  );
}