import { expect, test } from '@playwright/test'

// Minimal smoke test (US-10): load the page, send one message, assert a
// non-empty streamed response appears within timeout. Runs against
// whatever backend the dev server is configured for -- VITE_FUNCTION_URL
// in .env.local, i.e. the real deployed Lambda proxy, not the mock.
test('sends a message and receives a streamed response', async ({ page }) => {
  await page.goto('/')

  const input = page.getByLabel('Message')
  await input.fill("What are Ian's core skills?")
  await page.getByRole('button', { name: 'Send' }).click()

  const assistantMessage = page.locator('.message-assistant .message-text').last()

  // Streaming should produce non-empty text well before the full response
  // finishes -- this is the "incremental" part of the smoke test.
  await expect(assistantMessage).not.toHaveText('', { timeout: 15_000 })

  // Wait for the stream to finish (data-streaming flips to "false" on the
  // parent <li>) and assert the final text is non-empty and substantial.
  const assistantListItem = page.locator('li.message-assistant').last()
  await expect(assistantListItem).toHaveAttribute('data-streaming', 'false', {
    timeout: 20_000,
  })
  const finalText = await assistantMessage.textContent()
  expect(finalText?.trim().length ?? 0).toBeGreaterThan(0)
})
