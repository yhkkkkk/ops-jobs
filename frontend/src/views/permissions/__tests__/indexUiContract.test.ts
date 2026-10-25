import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

describe('permissions page UI migration contract', () => {
  it('uses Naive UI controls and Lucide status icons', () => {
    expect(source).toContain('<n-card')
    expect(source).toContain('<n-select')
    expect(source).toContain('<n-data-table')
    expect(source).toContain("from 'lucide-vue-next'")
    expect(source).not.toContain('<a-')
    expect(source).not.toContain('@arco-design/web-vue')
  })

  it('keeps permission check and user summary behavior', () => {
    expect(source).toContain('permissionsStore.fetchUserPermissions')
    expect(source).toContain('permissionsApi.checkPermission')
    expect(source).toContain('checkPermissions')
    expect(source).toContain('clearResults')
  })
})
