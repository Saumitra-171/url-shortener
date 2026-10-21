import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, setToken, setUnauthorizedHandler } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Only need to wait if a token exists: we have to ask the server who it belongs to.
  const [loading, setLoading] = useState(() => Boolean(getToken()));

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!getToken()) return;
    api.me().then(setUser).catch(() => {}).finally(() => setLoading(false));
  }, [logout]);

  const login = useCallback(async (email, password) => {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const register = useCallback(async (email, password) => {
    await api.register(email, password);
    await login(email, password);
  }, [login]);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}