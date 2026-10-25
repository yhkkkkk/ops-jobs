import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('execution records template props', () => {
  it('passes Arco select filterOption as a boolean binding', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

    expect(source).not.toMatch(/(?<!:)filter-option="false"/)
    expect(source).toContain(':filter-option="false"')
  })

  it('keeps secondary row actions behind a more menu', () => {
    const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')
    const actions = source

    expect(actions).toContain('h(NDropdown')
    expect(actions).toContain('MoreHorizontal')
    expect(actions).toContain('recordRowActions')
    expect(actions).not.toContain('重试历史 ({{ record.total_retry_count }})')
  })
})
