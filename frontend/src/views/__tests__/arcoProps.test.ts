import { readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const collectVueFiles = (dir: string): string[] => {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return collectVueFiles(path)
    return entry.isFile() && entry.name.endsWith('.vue') ? [path] : []
  })
}

describe('Arco template prop bindings', () => {
  it('passes filter-option false as a boolean binding', () => {
    const viewsDir = resolve(__dirname, '..')
    const offenders = collectVueFiles(viewsDir).filter((file) => {
      const source = readFileSync(file, 'utf8')
      return /(?<!:)filter-option="false"/.test(source)
    })

    expect(offenders.map((file) => relative(viewsDir, file))).toEqual([])
  })
})
