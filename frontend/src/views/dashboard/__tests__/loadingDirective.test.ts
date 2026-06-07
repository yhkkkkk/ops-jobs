import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('dashboard loading states', () => {
  it('does not use unregistered element-style v-loading directives', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/views/dashboard/index.vue'), 'utf8')

    expect(source).not.toContain('v-loading')
  })
})
