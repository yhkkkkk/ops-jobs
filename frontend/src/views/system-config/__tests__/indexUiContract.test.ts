import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(__dirname, '../index.vue'), 'utf8')

describe('system config page UI migration contract', () => {
  it('uses Naive UI controls and Lucide icons without Arco components', () => {
    expect(source).toContain('<n-tabs')
    expect(source).toContain('<n-form')
    expect(source).toContain('<n-data-table')
    expect(source).toContain('<n-modal')
    expect(source).toContain("from 'lucide-vue-next'")
    expect(source).not.toContain('<a-')
    expect(source).not.toContain('@arco-design/web-vue')
  })

  it('keeps all configuration tabs and save APIs', () => {
    expect(source).toContain('name="task"')
    expect(source).toContain('name="notification"')
    expect(source).toContain('name="agent"')
    expect(source).toContain('name="all"')
    expect(source).toContain('systemConfigApi.updateTaskConfig')
    expect(source).toContain('systemConfigApi.updateNotificationConfig')
    expect(source).toContain('systemConfigApi.updateAgentConfig')
    expect(source).toContain('systemConfigApi.updateConfig')
  })

  it('preserves sensitive value masking, JSON parsing, filtering, and pagination', () => {
    expect(source).toContain('SENSITIVE_CONFIG_VALUE')
    expect(source).toContain('isSensitiveConfigKey')
    expect(source).toContain('JSON.parse(trimmedText)')
    expect(source).toContain('categoryOptions')
    expect(source).toContain('onUpdatePage: handlePageChange')
    expect(source).toContain('onUpdatePageSize: handlePageSizeChange')
  })
})
