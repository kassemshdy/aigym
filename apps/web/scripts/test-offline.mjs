/**
 * The offline-sync contract's own test method (.agents/skills/offline-sync):
 * kill the network mid-session, log sets, reload (the power-cut case),
 * restore the network, and confirm exactly as many rows reach the server
 * as were logged — not fewer (lost) and not more (double-sent).
 *
 * Needs a real running stack, unlike scripts/shots.mjs — not part of
 * `npm run verify`.
 *
 *   cd apps/api
 *   bash scripts/bootstrap_db.sh && uv run alembic upgrade head
 *   AIGYM_SEED_MANAGER_PASSWORD=testpass123 uv run python scripts/seed.py
 *   uv run uvicorn app.main:app --port 8000 &
 *
 *   cd apps/web
 *   VITE_API_URL=http://localhost:8000 npm run build   # bakes the API URL in
 *   npx vite preview --port 5173 &                     # :5173 is what
 *                                                       # AIGYM_CORS_ORIGINS
 *                                                       # allows by default
 *   node scripts/test-offline.mjs
 *
 * Must be the production build served via `vite preview`, not `vite dev` —
 * the reload-while-offline step only works because the service worker
 * (registered only when import.meta.env.PROD) precached the shell.
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:5173'
const API = process.env.API ?? 'http://localhost:8000'
const USERNAME = process.env.SEED_USERNAME ?? 'kassem'
const PASSWORD = process.env.SEED_PASSWORD ?? 'testpass123'

function fail(message) {
  console.error(`FAIL: ${message}`)
  process.exit(1)
}

async function apiGet(path, token) {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) fail(`GET ${path} -> ${res.status}`)
  return res.json()
}

async function apiLogin() {
  const res = await fetch(`${API}/auth/staff/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  })
  if (!res.ok) fail(`API login failed: ${res.status} — is scripts/seed.py's password set to match SEED_PASSWORD?`)
  return (await res.json()).access_token
}

async function findMemberWithProgram(token) {
  const members = await apiGet('/members', token)
  for (const m of members) {
    const program = await apiGet(`/members/${m.id}/programs/active`, token)
    if (program?.exercises?.length) return m.id
  }
  fail('No member with an active program in the seed — run scripts/seed.py first')
}

async function main() {
  const token = await apiLogin()
  const memberId = await findMemberWithProgram(token)

  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium',
  })
  const context = await browser.newContext({ viewport: { width: 1024, height: 768 } })
  const page = await context.newPage()
  const pageErrors = []
  page.on('pageerror', (e) => pageErrors.push(e.message))

  await page.goto(`${BASE}/staff/login`)
  await page.getByPlaceholder('kassem').fill(USERNAME)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(`${BASE}/manager`)

  // Give the service worker time to install and start controlling the
  // page — the reload step below depends on it having precached the shell.
  await page.evaluate(() => navigator.serviceWorker.ready)

  await page.goto(`${BASE}/coach/session/${memberId}`)
  await page.getByRole('button', { name: /^Set \d/ }).waitFor({ timeout: 10_000 })

  const beforeWorkout = await apiGet(`/members/${memberId}/today-workout`, token)
  const sessionId = beforeWorkout.open_session_id
  if (!sessionId) fail('No open workout session after loading the session screen')
  const before = await apiGet(`/workout-sessions/${sessionId}`, token)
  const baseline = before.sets.length

  console.log('Killing the network and logging 3 sets...')
  await context.setOffline(true)
  for (let i = 0; i < 3; i++) {
    await page.getByRole('button', { name: /^Set \d/ }).click()
  }
  await page.getByText('3 waiting to sync').waitFor({ timeout: 5_000 })
  console.log('  pending badge reads 3 ✓')

  console.log('Reloading (power-cut case)...')
  await page.reload()
  await page.getByText('3 waiting to sync').waitFor({ timeout: 5_000 })
  console.log('  still queued after reload ✓')

  console.log('Restoring the network...')
  await context.setOffline(false)
  await page.getByText('Everything saved').waitFor({ timeout: 15_000 })
  console.log('  outbox drained ✓')

  const after = await apiGet(`/workout-sessions/${sessionId}`, token)
  const gained = after.sets.length - baseline
  if (gained !== 3) fail(`Expected exactly 3 new sets on the server, got ${gained}`)
  console.log(`  server has exactly 3 new rows, not ${gained === 3 ? 6 : gained} ✓`)

  if (pageErrors.length) fail(`Console/page errors during the run: ${pageErrors.join('; ')}`)

  await browser.close()
  console.log('PASS: offline outbox queued 3 sets, survived a reload, replayed exactly 3 on reconnect.')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
