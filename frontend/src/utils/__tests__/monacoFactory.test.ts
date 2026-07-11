import { describe, expect, it } from 'vitest'
import { shouldPreloadMonaco } from '../monacoFactory'

describe('monaco preload policy', () => {
  it('keeps monaco preload disabled by default for faster route switches', () => {
    expect(shouldPreloadMonaco()).toBe(false)
    expect(shouldPreloadMonaco(undefined)).toBe(false)
  })

  it('only enables monaco preload through an explicit flag', () => {
    expect(shouldPreloadMonaco('true')).toBe(true)
    expect(shouldPreloadMonaco('1')).toBe(false)
    expect(shouldPreloadMonaco('false')).toBe(false)
  })
})
