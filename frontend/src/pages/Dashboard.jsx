import { useAuth } from "../auth.jsx";

export default function Dashboard() {
  const { user } = useAuth();
  return (
    <div className="card">
      <h1>Your links</h1>
      <p className="muted">Logged in as {user.email}. The dashboard comes next.</p>
    </div>
  );
}