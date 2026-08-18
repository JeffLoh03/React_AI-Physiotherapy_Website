export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export function getAccessToken(): string | null {
  return localStorage.getItem('access_token');
}

export function clearAuth(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
  localStorage.removeItem('role');
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401) {
    clearAuth();
    if (window.location.pathname !== '/auth') window.location.assign('/auth');
  }
  return response;
}

export function authenticatedWebSocketUrl(): string {
  const base = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}token=${encodeURIComponent(getAccessToken() || '')}`;
}
