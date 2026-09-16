import {
  ApiKeySummary,
  AuthResponse,
  AuthUser,
  DashboardStats,
  JobDetail,
  JobSummary,
  LandRecord,
  SegmentResponse,
} from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const ACCESS_KEY = 'bhoomi_access_token';
const REFRESH_KEY = 'bhoomi_refresh_token';

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(ACCESS_KEY);
  } catch {
    return null;
  }
}

function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function storeTokens(access: string, refresh: string): void {
  try {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  } catch {
    /* private browsing / storage disabled: session just won't survive a refresh */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return false;
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json();
        localStorage.setItem(ACCESS_KEY, data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function authFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return authFetch(path, init, false);
  }
  return res;
}

async function authJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = text;
    try {
      detail = JSON.parse(text).detail || text;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Auth -----------------------------------------------------------

export async function register(
  email: string,
  password: string,
  name: string,
  state = '',
  district = ''
): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name, state, district }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || 'registration failed');
  }
  const data: AuthResponse = await res.json();
  storeTokens(data.access_token, data.refresh_token);
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || 'invalid email or password');
  }
  const data: AuthResponse = await res.json();
  storeTokens(data.access_token, data.refresh_token);
  return data;
}

export function logout(): void {
  clearTokens();
}

export async function fetchMe(): Promise<AuthUser> {
  return authJson<AuthUser>('/auth/me');
}

export async function listApiKeys(): Promise<ApiKeySummary[]> {
  return authJson<ApiKeySummary[]>('/auth/api-keys');
}

export async function createApiKey(name: string): Promise<ApiKeySummary & { key: string }> {
  return authJson('/auth/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export async function revokeApiKey(id: string): Promise<void> {
  await authJson(`/auth/api-keys/${id}`, { method: 'DELETE' });
}

// --- Health -----------------------------------------------------------

export async function checkBackendHealth(): Promise<{ online: boolean; latency: number }> {
  const start = performance.now();
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { cache: 'no-cache' });
    const latency = Math.round(performance.now() - start);
    return { online: res.ok, latency };
  } catch {
    return { online: false, latency: 0 };
  }
}

// --- Segmentation / OCR pipeline ---------------------------------------

export interface RunSegmentOptions {
  lang?: string;
  docType?: string;
  state?: string;
  district?: string;
  tehsil?: string;
  extractTables?: boolean;
  llmRefine?: boolean;
}

export async function runSegmentApi(file: File, opts: RunSegmentOptions = {}): Promise<SegmentResponse> {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('ocr', 'true');
  formData.append('extract_tables', String(opts.extractTables ?? true));
  formData.append('llm_refine', String(opts.llmRefine ?? true));
  formData.append('ocr_lang', opts.lang || 'en');
  formData.append('doc_type', opts.docType || 'auto');
  formData.append('state', opts.state || '');
  formData.append('district', opts.district || '');
  formData.append('tehsil', opts.tehsil || '');
  formData.append('include_images', 'true');

  const res = await authFetch('/segment', { method: 'POST', body: formData });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      detail = JSON.parse(text).detail || text;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, detail || `Backend error (${res.status})`);
  }
  return res.json();
}

// --- Jobs ---------------------------------------------------------------

export interface ListJobsParams {
  status?: string;
  state?: string;
  district?: string;
  mine?: boolean;
  limit?: number;
  offset?: number;
}

export async function listJobs(params: ListJobsParams = {}): Promise<{ total: number; jobs: JobSummary[] }> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') qs.set(k, String(v));
  });
  const query = qs.toString();
  return authJson(`/v1/jobs${query ? `?${query}` : ''}`);
}

export async function getJob(id: string): Promise<JobDetail> {
  return authJson(`/v1/jobs/${id}`);
}

export async function getStats(): Promise<DashboardStats> {
  return authJson('/v1/stats');
}

export async function editLine(jobId: string, index: number, text: string): Promise<{ index: number; text: string }> {
  return authJson(`/jobs/${jobId}/lines/${index}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
}

export async function editLandRecord(
  jobId: string,
  record: LandRecord
): Promise<{ land_record: LandRecord; validation: LandRecord['validation'] }> {
  return authJson(`/jobs/${jobId}/land-record`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  });
}

export async function verifyJob(id: string): Promise<JobSummary> {
  return authJson(`/v1/jobs/${id}/verify`, { method: 'POST' });
}

export async function rejectJob(id: string, reason: string): Promise<JobSummary> {
  return authJson(`/v1/jobs/${id}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
}

export async function deleteJob(id: string): Promise<void> {
  await authJson(`/jobs/${id}`, { method: 'DELETE' });
}

export function jobFileUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function downloadFile(filename: string, content: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
