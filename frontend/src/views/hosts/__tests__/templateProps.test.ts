import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('hosts template props', () => {
  it('passes Arco typography copyable as a boolean', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

    expect(source).not.toMatch(/:copyable="\{/)
    expect(source).toContain('copyable')
  })

  it('does not force a horizontal table scrollbar for the host list', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

    expect(source).not.toMatch(/:scroll="\{\s*x:/)
  })

  it('uses responsive filter sizing instead of fixed inline widths in the host toolbar', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')
    const toolbarStart = source.indexOf('<DataToolbar')
    const toolbarEnd = source.indexOf('</DataToolbar>', toolbarStart)
    const toolbar = source.slice(toolbarStart, toolbarEnd)

    expect(toolbar).not.toMatch(/style="width:\s*\d+px"/)
    expect(toolbar).toContain('class="filter-control')
  })
})
