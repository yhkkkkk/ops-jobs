const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api') as string;
const SSE_BASE_URL = (import.meta.env.VITE_SSE_BASE_URL || '/sse/sse') as string;

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

export { API_BASE_URL, SSE_BASE_URL };
