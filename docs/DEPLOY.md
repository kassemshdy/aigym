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

The `web` service now serves the real Phase 2 backend for the **manager** surface:
`VITE_API_URL` is set to the `api` service's domain, so manager screens read and write
live Postgres data through JWT-authenticated requests, and `/manager/login` gates them —
the open role switcher no longer applies to manager screens. Coach and member screens are
still Phase 1 mocks (member sign-in still accepts any code) until Phase 3/4 gives those
surfaces a backend.

**No real manager account exists on the live database yet** (see "Seeding real content"
below) — until that's done, `/manager/login` on the live URL has nothing to sign into.

## The API service (Phase 2)

**Status: provisioned, live, and `web` is pointed at it.** Postgres and `api` are both
running in the `aigym` project; `web`'s `VITE_API_URL` is
`https://api-production-6336.up.railway.app`, confirmed set on the service and baked into
the current live deployment (commit `05c9dfdc`, `SUCCESS`).

|  |  |
|---|---|
| API source | `kassemshdy/aigym`, branch `main`, root directory `/apps/api` |
| API build | `apps/api/Dockerfile` — installs with `uv`; container start runs `scripts/bootstrap_db.sh` (idempotent), then `alembic upgrade head`, then `uvicorn` |
| API health | `/health` — confirmed 200 in the deploy's own logs |
| API domain | `api-production-6336.up.railway.app` (Railway-generated, not custom) |
| Postgres | `postgres:16` image + a persistent volume at `/var/lib/postgresql/data` — **no public TCP proxy**, reachable only over Railway's private network as `postgres.railway.internal` |

### How the two services connect, and why Postgres has no public endpoint

`api`'s env vars (`PGHOST=postgres.railway.internal`, `PGUSER`/`PGPASSWORD` referencing
`${{Postgres.POSTGRES_USER}}`/`${{Postgres.POSTGRES_PASSWORD}}`) let its own container run
`scripts/bootstrap_db.sh` at every start, creating the `aigym_app` role
(`NOBYPASSRLS`, decision 16) over the private network. That is what let this get set up
without ever exposing the database to the public internet, even temporarily, for a
bootstrapping step — `AIGYM_DATABASE_URL` (the `aigym_app` role) and
`AIGYM_DATABASE_URL_MIGRATIONS` (Postgres's own superuser, used only by the container's own
`alembic upgrade head` and by `scripts/seed.py` if it's run from a Railway shell) both point
at `postgres.railway.internal:5432`, not a public host.

`AIGYM_JWT_SECRET` and `AIGYM_ONBOARDING_SECRET` are freshly generated 32-byte random
values, set directly on the `api` service — not the `.env.example` placeholders, and not
recorded anywhere outside Railway's own variable store. `AIGYM_CORS_ORIGINS` is
`["https://triple-a.up.railway.app"]` — the `web` origin only.

### Seeding real content (not yet done)

`uv run python scripts/seed.py`, run against `AIGYM_DATABASE_URL_MIGRATIONS` from a Railway
shell, loads Triple A Gym's actual members, plans, coaches and class schedule. Onboard the
real first manager through `POST /gyms` rather than the seed script, since the seeded staff
row has no PIN set. This is the remaining step between "the live URL runs on real
infrastructure" and "the live URL is actually usable by Triple A Gym" — until it's done,
the production database has no gyms at all and `/manager/login` cannot succeed.

### `web` is pointed at it

`VITE_API_URL` was set on `web` to the `api` service's domain and the service redeployed
— Vite bakes the value in at *build* time, not runtime, so this required (and got) a `web`
rebuild, not just an `api` change. This was done ahead of the original plan (which held it
back for API soak time and seeded content) on explicit instruction. The coach and member
surfaces are unaffected — they stay on mocks regardless of this variable, per the Phase 2
boundary in the root `AGENTS.md`.

### Why migrations run in the container's own start command, not a release step

Railway's Config as Code is what would normally carry a separate release command
(decision 15 rules it out) and Infrastructure as Code (`.railway/railway.ts`) is the
supported replacement but needs an interactive `railway login`, so it is not wired up yet.
`alembic upgrade head` running before `uvicorn` in the Dockerfile's `CMD` is the simplest
thing that is still correct **at one replica** — see `apps/api/AGENTS.md`'s note on moving
this to a real release command if this service is ever scaled beyond that.

### What cannot be verified from this environment

`*.up.railway.app` is unreachable from this sandbox (`connect_rejected` on CONNECT) — the
same restriction that already applies to `web`. What *is* verified: the build succeeded,
`scripts/bootstrap_db.sh` and all four migrations ran cleanly in the deploy's own logs, and
Railway's own healthcheck probe got `GET /health` → `200 OK` from inside Railway's network
— all confirmed via the Railway MCP tools rather than a direct request from here. A request
from outside Railway's network (a phone, a browser with real internet) is still the one
check this environment cannot do itself, same as `web`'s own deploys.
