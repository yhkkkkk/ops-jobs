import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const routerSource = readFileSync(resolve(testDir, '../../../router/index.ts'), 'utf8')
const startModalSource = readFileSync(resolve(testDir, '../components/FlowStartModal.vue'), 'utf8')

describe('flow task center contract', () => {
  it('separates the task center from the template library and creates named tasks', () => {
    const taskCenterSource = readFileSync(resolve(testDir, '../tasks.vue'), 'utf8')

    expect(routerSource).toContain("path: '/flows/tasks'")
    expect(taskCenterSource).toContain('class="flow-task-table"')
    expect(taskCenterSource).toContain('flowApi.getRuns')
    expect(taskCenterSource).not.toContain('任务 #${record.id}')
    expect(taskCenterSource).not.toContain('#{{ record.id }}')
    expect(startModalSource).toContain('label="任务名称"')
    expect(startModalSource).toContain('name: startForm.name')
  })
})