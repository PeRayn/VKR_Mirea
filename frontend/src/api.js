export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function api(path, options = {}, token, onUnauthorized) {
  const headers = { ...(options.headers ?? {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (response.status === 401 || response.status === 403) {
    if (onUnauthorized) onUnauthorized();
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}
