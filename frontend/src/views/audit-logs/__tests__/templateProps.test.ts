import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('audit logs template props', () => {
  it('passes Arco table column widths as number bindings', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

    expect(source).not.toMatch(/<a-table-column[^>]*\swidth="\d+"/)
    expect(source).not.toMatch(/<a-table-column[^>]*\smin-width="\d+"/)
    expect(source).toContain(':width="120"')
  })
})
