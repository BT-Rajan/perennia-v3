// ──────────────────────────────────────────────────────────
// Every call here is same-origin in dev via vite.config.js's proxy
// (so the session cookie set by the backend just works, no CORS
// dance needed) and expected to be same-origin in production too -
// see PASS7_NOTES.md for the deployment note. `credentials: "include"`
// is kept anyway as a safety net if this ever *is* cross-origin.
// ──────────────────────────────────────────────────────────

let csrfToken = null;

export function setCsrfToken(token) {
  csrfToken = token;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const method = options.method || "GET";
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const res = await fetch(`/${path}`, { credentials: "include", ...options, headers });

  if (res.status === 401) {
    throw new ApiError("Session expired — please log in again.", 401);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON; keep the generic message
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const adminApi = {
  login: (username, password) =>
    request("admin/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request("admin/api/auth/logout", { method: "POST" }),
  me: () => request("admin/api/auth/me"),

  statsOverview: () => request("admin/api/stats/overview"),

  listAppointments: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
    return request(`admin/api/booking/appointments?${qs}`);
  },
  cancelAppointment: (id) => request(`admin/api/booking/appointments/${id}/cancel`, { method: "POST" }),

  listLeads: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
    return request(`admin/api/leads?${qs}`);
  },
  getLead: (id) => request(`admin/api/leads/${id}`),
  updateLead: (id, body) => request(`admin/api/leads/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteLead: (id) => request(`admin/api/leads/${id}`, { method: "DELETE" }),
};

export { ApiError };
