import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('audit logs table props', () => {
  it('keeps audit table column widths as number literals', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

    expect(source).not.toMatch(/<a-table-column/)
    expect(source).toContain('<n-data-table')
    expect(source).toContain('width: 120')
  })
})
