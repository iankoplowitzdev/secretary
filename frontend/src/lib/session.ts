/**
 * Client-side session identifier.
 *
 * Generated once per tab load and held in memory only (module-level state).
 * Deliberately NOT persisted to localStorage/sessionStorage — a page refresh
 * or new tab should get a fresh session id.
 */

let sessionId: string | null = null

/**
 * Returns the current tab's session id, generating one on first call.
 * Subsequent calls within the same tab load always return the same value.
 */
export function getSessionId(): string {
  if (sessionId === null) {
    sessionId = crypto.randomUUID()
  }
  return sessionId
}

/**
 * Test-only helper to reset the in-memory session id so tests can verify
 * fresh-load behavior in isolation. Not used by application code.
 */
export function __resetSessionIdForTests(): void {
  sessionId = null
}
