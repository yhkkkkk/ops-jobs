import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

describe('users page UI migration contract', () => {
  it('uses Naive UI controls and Lucide actions', () => {
    expect(source).toContain('<n-data-table')
    expect(source).toContain('<n-input')
    expect(source).toContain('<n-modal')
    expect(source).toContain("from 'lucide-vue-next'")
    expect(source).not.toContain('<a-')
    expect(source).not.toContain('@arco-design/web-vue')
  })

  it('keeps user search, pagination, editing, and API behavior', () => {
    expect(source).toContain('authApi.getUsers')
    expect(source).toContain('authApi.updateUser')
    expect(source).toContain('handleSearch')
    expect(source).toContain('handlePageSizeChange')
    expect(source).toContain('editVisible')
  })
})
