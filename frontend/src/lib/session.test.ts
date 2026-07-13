import { describe, expect, it } from 'vitest'
import { __resetSessionIdForTests, getSessionId } from './session'

describe('session id', () => {
  it('is stable across multiple calls within the same tab load', () => {
    __resetSessionIdForTests()
    const first = getSessionId()
    const second = getSessionId()
    const third = getSessionId()
    expect(first).toBe(second)
    expect(second).toBe(third)
  })

  it('looks like a UUID', () => {
    __resetSessionIdForTests()
    const id = getSessionId()
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    )
  })

  it('is not persisted to localStorage or sessionStorage', () => {
    __resetSessionIdForTests()
    const id = getSessionId()
    expect(Object.values(localStorage)).not.toContain(id)
    expect(Object.values(sessionStorage)).not.toContain(id)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})
