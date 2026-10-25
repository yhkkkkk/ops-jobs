import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

describe('dashboard page UI migration contract', () => {
  it('uses Naive UI surfaces and Lucide icons', () => {
    expect(source).toContain('<n-card')
    expect(source).toContain('<n-button')
    expect(source).toContain('<n-spin')
    expect(source).toContain("from 'lucide-vue-next'")
    expect(source).not.toContain('<a-')
    expect(source).not.toContain('@arco-design/web-vue')
  })

  it('keeps dashboard data loading and navigation behavior', () => {
    expect(source).toContain('dashboardApi.getOverview')
    expect(source).toContain('dashboardApi.getRecentActivity')
    expect(source).toContain('favoriteApi.getFavorites')
    expect(source).toContain('refreshAllData')
    expect(source).toContain("router.push('/quick-execute')")
    expect(source).toContain("router.push('/execution-records')")
  })
})
