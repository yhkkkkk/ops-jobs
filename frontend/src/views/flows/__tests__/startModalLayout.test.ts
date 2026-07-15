import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const componentSource = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../components/FlowStartModal.vue'),
  'utf8',
)
const apiSource = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../../../api/ops.ts'),
  'utf8',
)

describe('flow start modal layout', () => {
  it('does not ask users to select an agent server when starting a flow', () => {
    expect(componentSource).not.toContain('调度 Agent Server')
    expect(componentSource).not.toContain('Agent Server ID')
    expect(componentSource).not.toContain('agent_server_id')
  })

  it('sends a task name and flow inputs without any agent server selector', () => {
    expect(apiSource).toContain('startTemplate(id: number, data: { name?: string; inputs?: Record<string, any> })')
    expect(apiSource).not.toContain('agent_server_id')
  })

  it('uses a global host variable textarea instead of asset selection or ids', () => {
    expect(componentSource).not.toContain('主机 ID，用逗号分隔')
    expect(componentSource).not.toContain('HostSelector')
    expect(componentSource).toContain('每行一个 IP 或主机名，可粘贴多行')
    expect(componentSource).not.toContain('节点参数覆盖')
    expect(componentSource).not.toContain('nodeOverrides')
  })
})
