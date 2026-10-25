import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(__dirname, '../../../..')

describe('UI migration foundation', () => {
  it('declares the new UI dependencies with Arco fully removed', () => {
    const packageJson = JSON.parse(readFileSync(resolve(frontendRoot, 'package.json'), 'utf8'))

    expect(packageJson.dependencies['naive-ui']).toBeTruthy()
    expect(packageJson.dependencies['lucide-vue-next']).toBeTruthy()
    expect(packageJson.dependencies['@arco-design/web-vue']).toBeUndefined()
  })

  it('registers only the Naive UI component resolver after the migration', () => {
    const viteConfig = readFileSync(resolve(frontendRoot, 'vite.config.ts'), 'utf8')

    expect(viteConfig).not.toContain('ArcoResolver')
    expect(viteConfig).toContain('NaiveUiResolver(),')
  })

  it('wraps the existing router shell with Naive UI providers', () => {
    const appSource = readFileSync(resolve(frontendRoot, 'src/App.vue'), 'utf8')

    for (const provider of ['n-config-provider', 'n-message-provider', 'n-notification-provider', 'n-dialog-provider']) {
      expect(appSource).toContain(provider)
    }
    expect(appSource).toContain('platformThemeOverrides')
    expect(appSource).toContain('<router-view />')
  })

  it('keeps the shared theme and icon vocabulary in one migration module', () => {
    const themeSource = readFileSync(resolve(frontendRoot, 'src/components/ui/theme.ts'), 'utf8')

    expect(themeSource).toContain('platformThemeOverrides')
    expect(themeSource).toContain('platformIcons')
    expect(themeSource).toContain("from 'lucide-vue-next'")
  })

  it('provides global 24-col form-grid styles after Arco row/col removal', () => {
    const css = readFileSync(resolve(frontendRoot, 'src/styles/app.css'), 'utf8')

    expect(css).toContain('.form-grid-row')
    expect(css).toContain('grid-template-columns: repeat(24, minmax(0, 1fr))')
    expect(css).toContain('.form-grid-col')
    expect(css).toContain('.page-header-block')
  })
})
