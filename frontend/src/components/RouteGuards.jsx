import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth.jsx";

// Pages that need a login. Remembers where the visitor was going, so login can send them back.
export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="center muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

// Login and register are pointless once you are logged in. This also performs the
// redirect after a successful login, so the forms never navigate by themselves.
export function GuestRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="center muted">Loading…</p>;
  if (user) return <Navigate to={location.state?.from?.pathname || "/"} replace />;
  return <Outlet />;
}