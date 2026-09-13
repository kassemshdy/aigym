# Deploy

The prototype runs on Railway at **https://triple-a.up.railway.app**

| | |
|---|---|
| Project | `aigym` (workspace PulseX) |
| Service | `web` (the Railway API cannot rename a service — cosmetic only, see below) |
| Region | `europe-west4` — closest of Railway's regions to Lebanon |
| Source | `kassemshdy/aigym`, branch `main`, root directory `/apps/web` |
| Build | `apps/web/Dockerfile` — Node builds, Caddy serves |
| Health | `/health` |
| Redeploys on | `main` moving, for anything under `apps/web/**` — i.e. a merge from `develop` |

The hostname is a **claimed** service domain, not the auto-generated one. Railway derives
`<service>-<environment>-<hash>.up.railway.app` from the service name by default, which gave
`web-production-ca41b` — machine noise, and not something to hand a gym owner. `triple-a` was
claimed explicitly, so the hostname no longer follows the service name. That is why the
service is still called `web` on the canvas while the URL reads `triple-a`: renaming a service
is dashboard-only, and now purely cosmetic.

## How it serves

`apps/web/Dockerfile` is a two-stage build: `node:22-alpine` runs `npm ci && npm run build`,
then `caddy:2-alpine` gets `dist/` and the `Caddyfile`. No Node process at runtime — the
running container is Caddy and a folder of static files.

`apps/web/Caddyfile` does four things that matter:

1. **SPA fallback** — `try_files {path} /index.html`. The app is a `BrowserRouter` SPA with
   20 client routes. Without this, every route except `/` returns 404 on a hard refresh or a
   pasted link, which would make the URL useless for the one thing it is for.
2. **`/health`** — responds `ok` without touching the app, so a broken build fails the
   healthcheck instead of looking healthy.
3. **Cache headers** — `/assets/*` is content-hashed by Vite, so it is immutable for a year.
   Everything else resolves to `index.html` and is `no-cache`. The matcher is
   `not path /assets/*` rather than a literal `/index.html`, because the literal form misses
   `/` and every deep link — and a stale shell surviving a redeploy points at hashed assets
   that no longer exist, which is a white screen.
4. **`auto_https off`** — Railway terminates TLS. Leaving Caddy's automatic HTTPS on breaks
   the deploy.

## There is no railway.json, on purpose

Railway's Config as Code (`railway.json` / `railway.toml`) is deprecated: existing files stop
being read on **2026-12-01**, and new services cannot opt into it at all. A `railway.json`
added for this service would never be read.

So configuration lives in two places instead:

- **The Dockerfile** — Railway always builds with a Dockerfile when it finds one, no config
  file involved.
- **Service settings** — root directory, healthcheck, watch patterns, restart policy. Set on
  the service itself (dashboard, CLI, or the Railway MCP).

The replacement for Config as Code is Infrastructure as Code (`.railway/railway.ts`),
evaluated by the Railway CLI with `railway config plan` / `railway config apply`. Worth
adopting once this project has more than one service — the API, worker, Postgres and Redis of
Phase 2 are a good reason. It needs the CLI and an interactive `railway login`, so it is done
from a developer machine, not from CI.

## Deploying a change

Work lands on `develop`. Deploying means merging it into `main`:

```bash
git checkout main && git merge --no-ff develop && git push origin main
git checkout develop
```

Anything under `apps/web/**` triggers a build. Changes only to `docs/` or `AGENTS.md` do not,
which is intended — documentation should not cost a deploy.

Pushing to `develop` never deploys. If you want a change on the live URL, it has to go through
the merge above; that is deliberate, since the URL is in the investor deck.

## When a deploy fails

```bash
# what happened
railway logs --build          # or the Railway MCP: get-logs types=["build"]
```

Failures seen so far and what they mean:

- **First-ever deployment failed immediately.** Expected. Creating a service from a GitHub
  repo triggers a build before the root directory can be set, so it builds the repo root,
  which has no Dockerfile. Set the root directory to `/apps/web` and push again.
- **Healthcheck fails but the build succeeded.** Caddy is not listening on `$PORT`. Check the
  `:{$PORT:3000}` line in the Caddyfile — Railway assigns the port at runtime.
- **Every route 404s except `/`.** The `try_files` line is gone or the `handle` block is
  malformed. `caddy validate --config Caddyfile --adapter caddyfile` catches most of it.

## Testing the serving layer locally

You do not need Docker to test the part most likely to break. Point a real Caddy at a real
build:

```bash
cd apps/web && npm run build
PORT=8080 caddy run --config Caddyfile --adapter caddyfile

curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/coach/session/m1   # 200, not 404
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/health             # 200
curl -sI localhost:8080/ | grep -i cache-control                           # no-cache
```

To check the whole deployed app rather than just the server, run the screenshot suite against
the live URL — it asserts correct direction, no overflow and no console errors on every screen
in both languages:

```bash
BASE=https://triple-a.up.railway.app node apps/web/scripts/shots.mjs ./shots
```

## What is deployed

Phase 1: the clickable prototype. Mock data, no backend, no database. Member sign-in accepts
any code and the role switcher lets any visitor open the manager and coach screens.

That is correct for a demo of entirely invented data, and it is exactly why **this URL must
not be pointed at real member data while it stays public.** Phase 2 brings real auth and
per-gym isolation; a password on the demo is about ten lines of Caddy `basic_auth` whenever
it is wanted.
