export type StatusVariant = 'success' | 'info' | 'warn' | 'danger' | 'muted'

const STATUS_VARIANTS: Record<string, StatusVariant> = {
  active: 'success',
  enabled: 'success',
  healthy: 'success',
  online: 'success',
  success: 'success',

  processing: 'info',
  running: 'info',

  pending: 'warn',
  retrying: 'warn',
  warning: 'warn',
  warn: 'warn',

  danger: 'danger',
  error: 'danger',
  failed: 'danger',

  cancelled: 'muted',
  disabled: 'muted',
  inactive: 'muted',
  offline: 'muted',
  unknown: 'muted',
}

const IGNORED_FILTER_KEYS = new Set(['page', 'page_size', 'pageSize', 'current'])

export function resolveStatusVariant(status?: string | null): StatusVariant {
  if (!status) return 'muted'
  return STATUS_VARIANTS[String(status).toLowerCase()] ?? 'muted'
}

export function countActiveFilters(filters: Record<string, unknown>): number {
  return Object.entries(filters).reduce((count, [key, value]) => {
    if (IGNORED_FILTER_KEYS.has(key)) return count
    if (value === undefined || value === null || value === '' || value === false) return count
    if (Array.isArray(value)) return value.length > 0 ? count + 1 : count
    return count + 1
  }, 0)
}

export function formatCompactNumber(value?: number | string | null): string {
  if (value === undefined || value === null || value === '') return '-'

  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return String(value)

  const absValue = Math.abs(numericValue)
  if (absValue < 1000) return String(numericValue)
  if (absValue < 1000000) return `${trimDecimal(numericValue / 1000)}k`
  return `${trimDecimal(numericValue / 1000000)}m`
}

function trimDecimal(value: number): string {
  return value.toFixed(1).replace(/\.0$/, '')
}
