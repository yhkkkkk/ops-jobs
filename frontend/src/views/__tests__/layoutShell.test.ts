import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const layouts = ['../Layout.vue', '../OpsLayout.vue']

describe('layout shell behavior', () => {
  it('hides the default Arco sider trigger in both platform layouts', () => {
    for (const layout of layouts) {
      const source = readFileSync(resolve(__dirname, layout), 'utf8')

      expect(source).toContain(':hide-trigger="true"')
    }
  })

  it('centers collapsed menu icons instead of leaving labels or offsets', () => {
    for (const layout of layouts) {
      const source = readFileSync(resolve(__dirname, layout), 'utf8')

      expect(source).toContain('.arco-layout-sider-collapsed')
      expect(source).toContain('justify-content: center')
      expect(source).toContain('margin-right: 0')
    }
  })
})
