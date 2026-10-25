import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(__dirname, '../components/AccountForm.vue'), 'utf8')

describe('account form UI migration contract', () => {
  it('uses Naive UI form controls and Lucide feedback icons', () => {
    expect(source).toContain('<n-modal')
    expect(source).toContain('<n-form')
    expect(source).toContain('<n-input')
    expect(source).toContain('<n-radio-group')
    expect(source).toContain("from 'naive-ui'")
    expect(source).toContain("from 'lucide-vue-next'")
    expect(source).not.toContain('<a-')
    expect(source).not.toContain('@arco-design/web-vue')
  })

  it('keeps account create/update behavior and validation contract', () => {
    expect(source).toContain('accountApi.createAccount')
    expect(source).toContain('accountApi.updateAccount')
    expect(source).toContain('emit(\'success\')')
    expect(source).toContain('密码和私钥只能填写一个')
    expect(source).toContain('v-model:show="modalVisible"')
  })
})
