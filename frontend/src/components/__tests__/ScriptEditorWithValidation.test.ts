import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../ScriptEditorWithValidation.vue'), 'utf8')

describe('ScriptEditorWithValidation editor options', () => {
  it('uses the same compact gutter defaults as the shared Monaco editor', () => {
    expect(source).toContain('glyphMargin: false')
    expect(source).toContain('lineDecorationsWidth: 10')
    expect(source).toContain('lineNumbersMinChars: 3')
  })
})
