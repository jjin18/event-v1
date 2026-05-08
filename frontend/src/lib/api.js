/**
 * Offline-aware fetch wrappers.
 * All judge score writes go through the service worker (fake 200 offline).
 */

function getToken() {
  return localStorage.getItem("judge_token") || "";
}

function getAdminToken() {
  return localStorage.getItem("admin_token") || "";
}

async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---- Judge auth ----

export async function authByQR(token) {
  return apiFetch("/api/judge/auth/qr", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function authByPIN(pin, eventId) {
  return apiFetch("/api/judge/auth/pin", {
    method: "POST",
    body: JSON.stringify({ pin, event_id: eventId }),
  });
}

// ---- Judge data ----

export async function fetchJudgeProjects() {
  return apiFetch("/api/judge/projects", {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
}

export async function fetchJudgeScores() {
  return apiFetch("/api/judge/scores", {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
}

export async function submitScore(data) {
  return apiFetch("/api/judge/scores", {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify(data),
  });
}

// ---- Admin auth ----

export async function adminLogin(password, eventId = 0) {
  return apiFetch("/api/admin/auth", {
    method: "POST",
    body: JSON.stringify({ password, event_id: eventId }),
  });
}

// ---- Admin events ----

export async function fetchEvents() {
  return apiFetch("/api/admin/events", {
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

export async function createEvent(data) {
  return apiFetch("/api/admin/events", {
    method: "POST",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
    body: JSON.stringify(data),
  });
}

export async function updateEvent(id, data) {
  return apiFetch(`/api/admin/events/${id}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
    body: JSON.stringify(data),
  });
}

// ---- Admin projects ----

export async function fetchProjects(eventId) {
  return apiFetch(`/api/admin/projects?event_id=${eventId}`, {
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

export async function createProject(data) {
  return apiFetch("/api/admin/projects", {
    method: "POST",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
    body: JSON.stringify(data),
  });
}

export async function updateProject(id, data) {
  return apiFetch(`/api/admin/projects/${id}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
    body: JSON.stringify(data),
  });
}

export async function deleteProject(id) {
  return apiFetch(`/api/admin/projects/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

// ---- Admin judges ----

export async function fetchJudges(eventId) {
  return apiFetch(`/api/admin/judges?event_id=${eventId}`, {
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

export async function createJudge(data) {
  return apiFetch("/api/admin/judges", {
    method: "POST",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
    body: JSON.stringify(data),
  });
}

export async function deleteJudge(id) {
  return apiFetch(`/api/admin/judges/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

export async function regenerateQR(judgeId) {
  return apiFetch(`/api/admin/judges/${judgeId}/regenerate-qr`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

// ---- Admin exports ----

export function exportUrl(path, eventId) {
  const token = getAdminToken();
  return `${path}?event_id=${eventId}&token_override=1`;
}

export async function fetchLeaderboard(eventId) {
  return apiFetch(`/api/admin/leaderboard?event_id=${eventId}`, {
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
}

export function downloadWithAuth(url) {
  const token = getAdminToken();
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then((r) => r.blob())
    .then((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = url.split("/").pop().split("?")[0];
      a.click();
    });
}
