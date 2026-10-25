import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const landing = readFileSync(resolve(__dirname, '../Landing.vue'), 'utf8')
const notFound = readFileSync(resolve(__dirname, '../NotFound.vue'), 'utf8')

describe('entry pages UI migration contract', () => {
  it('uses Naive UI controls on the landing page', () => {
    expect(landing).toContain('<n-button')
    expect(landing).toContain("router.push('/login')")
    expect(landing).not.toContain('<a-')
    expect(landing).not.toContain('@arco-design/web-vue')
  })

  it('keeps the not-found recovery action', () => {
    expect(notFound).toContain('<n-result')
    expect(notFound).toContain('<n-button')
    expect(notFound).toContain("router.push('/dashboard')")
    expect(notFound).not.toContain('<a-')
  })
})
