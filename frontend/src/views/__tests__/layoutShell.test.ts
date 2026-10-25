import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const jobLayout = readFileSync(resolve(__dirname, '../Layout.vue'), 'utf8')
const opsLayout = readFileSync(resolve(__dirname, '../OpsLayout.vue'), 'utf8')
const layouts = [
  { name: 'job', source: jobLayout },
  { name: 'ops', source: opsLayout },
]

describe('layout shell behavior', () => {
  it('uses Naive UI shell primitives in both platform layouts', () => {
    for (const { source } of layouts) {
      expect(source).toContain('<n-layout')
      expect(source).toContain('<n-layout has-sider')
      expect(source).toContain('class="layout"')
      expect(source).toContain(':collapsed="collapsed"')
      expect(source).toMatch(/:?collapsed-width="64"/)
      expect(source).toContain(':collapsed-width="64"')
      expect(source).toContain("justify-content: flex-start")
      expect(source).toContain('min-width: 0 !important')
      expect(source).toContain('.n-menu--collapsed .n-menu-item-content__icon')
      expect(source).toContain('margin-right: 0 !important')
      expect(source).not.toContain('compactNavItems')
      expect(source).not.toContain('compact-nav')
      expect(source).toContain('<n-layout-sider')
      expect(source).toContain('<n-drawer')
      expect(source).toContain('v-model:show="mobileMenuOpen"')
      expect(source).toContain('MOBILE_BREAKPOINT = 520')
      expect(source).toContain('window.innerWidth <= MOBILE_BREAKPOINT')
      expect(source).toContain("window.addEventListener('resize'")
      expect(source).toContain('mobileMenuOpen.value = false')
      expect(source).toContain('<n-menu')
      expect(source).toContain('<n-breadcrumb')
      expect(source).toContain("from 'lucide-vue-next'")
      expect(source).not.toContain('<a-layout')
      expect(source).not.toContain('@arco-design/web-vue')
      expect(source).toContain('height: 68px')
      expect(source).toContain('min-height: 64px')
      expect(source).toContain('padding: 28px')
    }
  })

  it('keeps the key platform routes and switching actions visible', () => {
    for (const { source } of layouts) {
      expect(source).toContain('selected_platform')
      expect(source).toContain("router.replace('/login')")
      expect(source).toContain('仪表盘')
    }

    expect(jobLayout).toContain('作业平台')
    expect(jobLayout).toContain('切换到运维台')
    expect(opsLayout).toContain('运维台')
    expect(opsLayout).toContain('切换到作业平台')
  })

  it('keeps job workspaceMode auto-collapse without compact-nav', () => {
    expect(jobLayout).toContain('workspaceMode')
    expect(jobLayout).toContain('content--workspace')
    expect(jobLayout).toContain('previousCollapsedState')
    expect(jobLayout).toContain("route.meta.workspaceMode === true")
    expect(opsLayout).not.toContain('workspaceMode')
    expect(opsLayout).not.toContain('content--workspace')
  })

  it('keeps shell scripts readable instead of single-line dumps', () => {
    for (const { name, source } of layouts) {
      const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)?.[1] ?? ''
      const style = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? ''
      const longScriptLines = script.split('\n').filter((line) => line.length > 220)
      const longStyleLines = style.split('\n').filter((line) => line.length > 220)

      expect(script.length, `${name} script missing`).toBeGreaterThan(0)
      expect(style.length, `${name} style missing`).toBeGreaterThan(0)
      expect(longScriptLines, `${name} has minified script lines`).toEqual([])
      expect(longStyleLines, `${name} has minified style lines`).toEqual([])
      expect(source).toContain('const collapsed = ref(false)')
      expect(source).toMatch(/\nconst selectedKeys = ref/)
    }
  })
})
