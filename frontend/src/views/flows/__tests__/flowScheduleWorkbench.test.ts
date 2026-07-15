import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const flowSource = readFileSync(resolve(testDir, '../components/FlowTemplateWorkbench.vue'), 'utf8')
const scheduleDrawerSource = readFileSync(resolve(testDir, '../components/FlowScheduleDrawer.vue'), 'utf8')
const apiSource = readFileSync(resolve(testDir, '../../../api/ops.ts'), 'utf8')
const typesSource = readFileSync(resolve(testDir, '../../../types/index.ts'), 'utf8')

describe('flow schedule workbench contract', () => {
  it('keeps flow schedules scoped to the shared template workbench and its global variables', () => {
    expect(apiSource).toContain('getSchedules(params?: { template?: number })')
    expect(apiSource).toContain("'/flows/schedules/'")
    expect(apiSource).toContain('getScheduleRuns')
    expect(typesSource).toContain('export interface FlowSchedule')
    expect(flowSource).toContain("import FlowScheduleDrawer from './FlowScheduleDrawer.vue'")
    expect(flowSource).toContain('scheduleDrawerVisible')
    expect(flowSource).toContain('定时调度')
    expect(flowSource).toContain('<FlowScheduleDrawer')
    expect(scheduleDrawerSource).toContain('最近启动')
    expect(scheduleDrawerSource).toContain('重叠触发策略')
    expect(scheduleDrawerSource).toContain('错过触发策略')
    expect(scheduleDrawerSource).toContain('每行一个 IP 或主机名，可粘贴多行')
    expect(scheduleDrawerSource).not.toContain('hostOptions')
    expect(scheduleDrawerSource).not.toContain('实例 #${run.flow_run_id}')
    expect(typesSource).toContain('overlap_policy')
    expect(typesSource).toContain('misfire_policy')
    expect(typesSource).toContain('misfire_grace_seconds')
    expect(flowSource).toContain(':template="currentTemplate"')
    expect(flowSource).not.toContain('agent_server_id')
  })
})