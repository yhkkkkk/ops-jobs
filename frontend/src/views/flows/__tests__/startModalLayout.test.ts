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

  it('sends only flow inputs through the start template API payload', () => {
    expect(apiSource).toContain('startTemplate(id: number, data: { inputs?: Record<string, any> })')
    expect(apiSource).not.toContain('startTemplate(id: number, data: { inputs?: Record<string, any>; agent_server_id: number })')
  })

  it('does not expose host ids as the default host-list variable prompt', () => {
    expect(componentSource).not.toContain('主机 ID，用逗号分隔')
    expect(componentSource).toContain('主机地址或主机标识，用逗号分隔')
  })
})
