const TOKEN_KEY = "token";

// Wrapped in try/catch because storage can be blocked (private mode, strict settings).
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* the session just won't survive a refresh */ }
}
export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* nothing to clear */ }
}

export class ApiError extends Error {
  constructor(status, message, retryAfter = null) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter; // seconds, from the Retry-After header on a 429
  }
}

// The auth context registers a function here, so an expired token logs the user out
// from one place instead of every caller handling 401 itself.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

// FastAPI sends detail as a string (our own errors) or a list (validation errors).
function errorMessage(response, data) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = e.loc?.[e.loc.length - 1];
        const message = String(e.msg || "").replace(/^Value error, /, "");
        return field && field !== "body" ? `${field}: ${message}` : message;
      })
      .join(" ");
  }
  return `Request failed (${response.status}).`;
}

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  let payload;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (form) {
    payload = new URLSearchParams(form); // fetch sets the form content type itself
  }
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }

  if (response.status === 204) return null;

  let data = null;
  try { data = await response.json(); } catch { /* the body was not JSON */ }
  if (response.ok) return data;

  if (response.status === 401 && auth && token) onUnauthorized(); // the token expired or is invalid

  let message = errorMessage(response, data);
  const retryAfter = Number(response.headers.get("Retry-After")) || null;
  if (response.status === 429 && retryAfter) message += ` Try again in ${retryAfter}s.`;
  throw new ApiError(response.status, message, retryAfter);
}

export const api = {
  register: (email, password) =>
    request("/auth/register", { method: "POST", body: { email, password }, auth: false }),
  // The login route uses the OAuth2 form format, where the email field is called "username".
  login: (email, password) =>
    request("/auth/login", { method: "POST", form: { username: email, password }, auth: false }),
  me: () => request("/auth/me"),
};