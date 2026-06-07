import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('audit logs page shell', () => {
  it('uses the shared app page components instead of the legacy card header shell', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

    expect(source).toContain('<PageHeader')
    expect(source).toContain('<DataToolbar')
    expect(source).toContain('<DetailPanel')
    expect(source).toContain("from '@/components/app'")
    expect(source).not.toContain('class="page-header"')
    expect(source).not.toMatch(/<a-card class="mb-4"/)
  })
})
