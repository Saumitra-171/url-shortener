import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Register() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(email.trim(), password);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card auth-card">
      <h1>Create account</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="email" required
               value={email} onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="new-password" required
               minLength={8} maxLength={72}
               value={password} onChange={(e) => setPassword(e.target.value)} />
        <p className="hint">At least 8 characters.</p>

        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="muted">Already registered? <Link to="/login">Log in</Link></p>
    </div>
  );
}