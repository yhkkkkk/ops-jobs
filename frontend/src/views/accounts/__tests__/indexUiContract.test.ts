import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

describe('accounts page UI migration contract', () => {
  it('uses Naive UI table, filters, actions, and lucide icons', () => {
    expect(source).toContain('<n-data-table')
    expect(source).toContain('<n-input')
    expect(source).toContain('<n-select')
    expect(source).toContain("from 'lucide-vue-next'")
    expect(source).not.toContain('<a-table')
    expect(source).not.toContain('<a-input')
    expect(source).not.toContain('<a-select')
    expect(source).not.toContain('@arco-design/web-vue')
  })

  it('keeps account permissions and AccountForm integration', () => {
    expect(source).toContain("resourceType: 'serveraccount'")
    expect(source).toContain('<AccountForm')
    expect(source).toContain('accountApi.getAccounts')
    expect(source).toContain('accountApi.deleteAccount')
    expect(source).toContain('if (!permissionsStore.permissionCache.has(cacheKey)) return false')
  })
})
