const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api') as string;
const SSE_BASE_URL = (import.meta.env.VITE_SSE_BASE_URL || '/sse/sse') as string;
const MOCK_API_ENABLED = String(import.meta.env.VITE_MOCK_API || '').toLowerCase() === 'true';
const MOCK_API_STRICT = String(import.meta.env.VITE_MOCK_API_STRICT ?? (MOCK_API_ENABLED ? 'true' : 'false')).toLowerCase() !== 'false';
const MOCK_LATENCY_MS = Number(import.meta.env.VITE_MOCK_LATENCY_MS || 240);

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const joinUrl = (base: string, path: string) => {
  return `${trimTrailingSlash(base)}/${path.replace(/^\/+/, '')}`;
};

export const buildApiUrl = (path: string) => joinUrl(API_BASE_URL, path);

export const buildSseUrl = (path: string, query?: string) => {
  const url = joinUrl(SSE_BASE_URL, path);
  if (!query) return url;
  return `${url}?${query.replace(/^\?/, '')}`;
};

export { API_BASE_URL, SSE_BASE_URL, MOCK_API_ENABLED, MOCK_API_STRICT, MOCK_LATENCY_MS };
