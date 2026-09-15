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

Triple A Gym's real content is seeded on the live database. Staff sign in with **username +
password** (decision 21 — not phone + PIN, which this section described before that changed).
The first account is `kassem` / `super_admin` — see "Seeding real content" below for how to
set its password, add more staff accounts, or do either again for a second gym.

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
`alembic upgrade head` and by `scripts/seed.py`/`scripts/set_staff_password.py` when run via
`railway ssh`) both point at `postgres.railway.internal:5432`, not a public host.

`AIGYM_JWT_SECRET` and `AIGYM_ONBOARDING_SECRET` are freshly generated 32-byte random
values, set directly on the `api` service — not the `.env.example` placeholders, and not
recorded anywhere outside Railway's own variable store. `AIGYM_CORS_ORIGINS` is
`["https://triple-a.up.railway.app"]` — the `web` origin only.

### Seeding real content, and setting the manager's password

`scripts/seed.py` runs automatically on every `api` deploy, as the service's Railway
**Pre-Deploy Command** (`uv run python scripts/seed.py`, set via the Railway MCP's
`update-service`). It's idempotent — deletes and re-inserts by fixed id — so this costs
nothing on a deploy where the seed data hasn't changed, and it's what makes editing the
seed data (a new class time, a corrected plan price) ship the same way as any other code
change, with no manual step after merging. There is no separate GitHub Actions job for
this: GitHub Actions runs the test suite (including running `seed.py` against a throwaway
CI database, to prove the script itself works) as the merge gate; Railway's Pre-Deploy
Command is what actually seeds the one database that matters, right before the new
container starts serving.

It also creates the first account (`username: kassem`, `role: super_admin` — decision 21)
the first time it runs — but never touches `password_hash` on a row that already has one.
A password is normally chosen interactively (see below), never baked into seed data, so
re-seeding a database that already has one set never logs the account out.

**`AIGYM_SEED_MANAGER_PASSWORD`** (optional, unset by default; renamed from
`AIGYM_SEED_MANAGER_PIN` when staff login moved to username + password) is the one
exception: if `kassem`'s `password_hash` is still `NULL` and this variable is set, seeding
hashes it in as a one-time bootstrap default. It still never touches a row that already has
a real password. This exists to unblock a first login without an interactive `railway ssh`
session; change it to a real password via `set_staff_password.py` once you're in, and unset
the variable afterward so it doesn't linger as a known credential.

```bash
railway ssh -s api -- uv run python scripts/set_staff_password.py
```

Prompts for username and password (via `getpass`, so neither lands in shell history) and
hashes it onto the matching `staff_users` row — this is the normal way to set or reset any
staff member's password, `AIGYM_SEED_MANAGER_PASSWORD` bootstrap aside. Works for any
username already in the database, not just `kassem`.

**Adding Karim, Abed, or any other staff account** goes through the API now, not a script:
`POST /staff`, gated to `super_admin` (decision 21). Sign in as `kassem`, then:

```bash
curl -X POST https://api-production-6336.up.railway.app/staff \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Idempotency-Key: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -H "Content-Type: application/json" \
  -d '{"username":"karim","password":"...","name":"Karim","phone":"+961...","role":"coach"}'
```

`role` is `"manager"`, `"coach"`, or `"super_admin"` — nothing stops a super_admin creating
another one.

Do **not** use `POST /gyms` to create the real manager account after seeding — it creates a
brand-new gym and a brand-new `staff_users` row, and a second row sharing the seeded
manager's phone number breaks `staff_login`'s lookup (it expects exactly one match). `POST
/gyms` is for onboarding a gym that has no seed data at all.

### `web` is pointed at it

`VITE_API_URL` was set on `web` to the `api` service's domain and the service redeployed
— Vite bakes the value in at *build* time, not runtime, so this required (and got) a `web`
rebuild, not just an `api` change. This was done ahead of the original plan (which held it
back for API soak time and seeded content) on explicit instruction. The coach and member
surfaces are unaffected — they stay on mocks regardless of this variable, per the Phase 2
boundary in the root `AGENTS.md`.

### Why bootstrap, migrate and seed all run as the Pre-Deploy Command, not in the start command

They used to run at the top of the Dockerfile's `CMD`, before `uvicorn` — simplest thing that
was still correct at one replica (decision 15 rules out Config as Code's release-command
feature; Infrastructure as Code, `.railway/railway.ts`, is the supported replacement but needs
an interactive `railway login`, so it isn't wired up). That broke the moment `scripts/seed.py`
started running as the service's Railway **Pre-Deploy Command** (added later, so this and
seed's own doc comment can drift out of sync — check both if this area gets touched again):
Pre-Deploy Command runs in a separate one-off container **before** the new image's `CMD` ever
starts, on whatever schema the *previous* deployment left behind. A migration landing in the
same deploy as a seed.py change that depends on its new column — exactly what commit
`18a880e` did — makes seed.py 500 on a column that doesn't exist yet, since the migration
hadn't run. Failed at the `PRE_DEPLOY_COMMAND` stage in Railway's own deploy logs; the
previous successful deployment kept serving traffic throughout (Railway doesn't cut over a
failed deploy), so nothing user-facing broke, but every deploy after that would have failed
the same way until fixed.

Fixed by moving `bootstrap_db.sh && alembic upgrade head` into the Pre-Deploy Command too,
ahead of `seed.py`, so all three run in the correct order on the correct (new) schema before
anything starts serving. The Dockerfile's `CMD` is now just `uvicorn`. Still correct only at
one replica, same as before — concurrent replicas would race to bootstrap/migrate/seed
identically to the old design, just relocated.

### What cannot be verified from this environment

`*.up.railway.app` is unreachable from this sandbox (`connect_rejected` on CONNECT) — the
same restriction that already applies to `web`. What *is* verified: the build succeeds,
`scripts/bootstrap_db.sh`, all migrations, and `seed.py` all run cleanly in that exact order
when run locally end-to-end against a real (emptied) local Postgres, and Railway's own
healthcheck probe got `GET /health` → `200 OK` from inside Railway's network on prior
deploys — confirmed via the Railway MCP tools rather than a direct request from here. A
request from outside Railway's network (a phone, a browser with real internet) is still the
one check this environment cannot do itself, same as `web`'s own deploys.
