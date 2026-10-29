// Small wrappers around the backend API. All calls go to our own backend (/api, /ws),
// never to Gemini directly.

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  options: () => request("/api/options"),
  forms: () => request("/api/forms"),
  startSession: (form_id, settings) =>
    request("/api/session", { method: "POST", body: JSON.stringify({ form_id, settings }) }),
  endSession: (callId) => request(`/api/session/${callId}/end`, { method: "POST" }),
  simulate: (form_id, settings, speed = 1) =>
    request("/api/simulate", { method: "POST", body: JSON.stringify({ form_id, settings, speed }) }),
  report: (callId) => request(`/api/calls/${callId}`),
  review: (callId, reviews) =>
    request(`/api/calls/${callId}/review`, { method: "POST", body: JSON.stringify({ reviews }) }),
  exportUrl: (callId, format, section = "fields") =>
    `/api/calls/${callId}/export?format=${format}&section=${section}`,

  // Post-Call Report Module API
  getPostCallReport: (callId) => request(`/api/calls/${callId}/report`),
  generatePostCallReport: (callId, body = {}) =>
    request(`/api/calls/${callId}/report`, { method: "POST", body: JSON.stringify(body) }),
  saveRatings: (callId, ratings) =>
    request(`/api/calls/${callId}/ratings`, { method: "POST", body: JSON.stringify(ratings) }),
  getPostCallExportUrl: (callId, format = "json") =>
    `/api/calls/${callId}/report/export?format=${format}`,
  getSampleReports: () => request("/api/sample-reports"),
  getSampleReport: (provider) => request(`/api/sample-reports/${provider}`),
};


function wsUrl(path) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}

export const eventsSocketUrl = (callId) => wsUrl(`/api/calls/${callId}/events`);
export const callSocketUrl = (path) => wsUrl(path);
