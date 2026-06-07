import { describe, expect, it } from 'vitest'

import { countActiveFilters, formatCompactNumber, resolveStatusVariant } from '../uiPrimitives'

describe('app ui primitives', () => {
  it('maps backend status values to stable visual variants', () => {
    expect(resolveStatusVariant('success')).toBe('success')
    expect(resolveStatusVariant('online')).toBe('success')
    expect(resolveStatusVariant('running')).toBe('info')
    expect(resolveStatusVariant('pending')).toBe('warn')
    expect(resolveStatusVariant('failed')).toBe('danger')
    expect(resolveStatusVariant('offline')).toBe('muted')
    expect(resolveStatusVariant('unknown')).toBe('muted')
  })

  it('counts only meaningful active filters', () => {
    expect(countActiveFilters({
      name: 'deploy',
      status: '',
      tags: [],
      owner: undefined,
      dateRange: ['2026-06-01', '2026-06-07'],
      includeArchived: false,
      page: 1,
    })).toBe(2)
  })

  it('formats metric values without hiding operational scale', () => {
    expect(formatCompactNumber(987)).toBe('987')
    expect(formatCompactNumber(15200)).toBe('15.2k')
    expect(formatCompactNumber(null)).toBe('-')
  })
})
