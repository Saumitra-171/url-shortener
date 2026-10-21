import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">URL Shortener</Link>
        {user && (
          <div className="topbar-right">
            <span className="muted">{user.email}</span>
            <button className="btn btn-ghost" onClick={logout}>Log out</button>
          </div>
        )}
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}