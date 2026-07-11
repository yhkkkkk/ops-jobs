import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const businessExecutionPages = [
  '../QuickExecute.vue',
  '../execution-plans/execute.vue',
  '../job-templates/detail.vue',
  '../scheduled-tasks/editor.vue'
]

describe('automatic Agent-Server routing', () => {
  it('does not expose Agent-Server selection in business execution pages', () => {
    for (const page of businessExecutionPages) {
      const source = readFileSync(resolve(__dirname, page), 'utf8')

      expect(source).not.toContain('selectedAgentServerId')
      expect(source).not.toContain('请选择 Agent-Server')
      expect(source).not.toContain('agent_server_id')
      expect(source).not.toContain('fetchAgentServers')
    }
  })

  it('does not require Agent-Server in quick execution API types', () => {
    const source = readFileSync(resolve(__dirname, '../../api/ops.ts'), 'utf8')
    const quickApi = source.slice(source.indexOf('export const quickExecuteApi'))

    expect(quickApi).not.toContain('agent_server_id')
  })
})
