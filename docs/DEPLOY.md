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

The `web` service serves the real backend for all three surfaces now: `VITE_API_URL` is
set to the `api` service's domain, so manager, coach, and member screens all read and
write live Postgres data through JWT-authenticated requests. `/manager/login` gates staff
screens (manager and coach share one staff login, decision 21) and `/login` gates member
screens with a real phone + WhatsApp code (decision 13) — the open role switcher's
tap-through behavior only applies when `VITE_API_URL` is unset at all (local mock-mode
development). AI-draft-inbox and the two chat assistants are the one surface still on
mocks, deliberately — Phase 5's job (decision 10 needs the AI layer to exist first).

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
| Media volume | Railway Volume named `media`, mounted on `api` at `/data/media`; `AIGYM_MEDIA_ROOT` set to match (decision 28, Phase 4) |

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

### The media volume (Phase 4)

Progress photos and food-entry photos land on a Railway Volume, not S3/R2 (decision 28) —
provisioned directly against the live `api` service (not just described in code): a volume
named `media`, mounted at `/data/media`, with `AIGYM_MEDIA_ROOT=/data/media` set to match.
`app/storage.py` reads and writes under that path; nothing else on the service touches it.
Single-replica constraint, same one already accepted for Postgres — two `api` replicas
would each see their own empty mount, not a shared one.

**What is and isn't verified for this piece specifically:** the volume attach and the
service redeploy that followed both came back `SUCCESS` (confirmed via the Railway MCP
tools), and the exact same upload/read/delete code path was proven correct end-to-end
against a local disk mount (`apps/api/tests/test_storage.py`, `test_media.py`,
`test_food_entries.py`, `test_progress_photos.py`). What has **not** been separately
confirmed is a real photo upload actually round-tripping through the live Railway mount
itself — this environment can't reach `*.up.railway.app` to drive that (same restriction
noted throughout this file), and no member has used the live product yet to exercise it
naturally. Worth a manual check the first time a real gym member uploads a photo.

### The Anthropic key (Phase 5) — not set yet

**`AIGYM_ANTHROPIC_API_KEY` is not set on the live `api` service.** Until it is, every AI
route — member chat, food-photo estimates, and the coach's "suggest a plan" action —
answers **503, by design rather than by accident**: `app/ai/client.py` raises a typed
`AnthropicNotConfigured` that routes turn into a 503, so an un-keyed deployment degrades
predictably instead of 500-ing (decision 29). Nothing else in the product is affected; the
screens that don't call Claude behave exactly as they did in Phase 4.

Setting it is a dashboard/CLI step against Railway's own variable store, on the `api`
service, alongside the other secrets above — never committed, and `.env.example` carries a
placeholder only. Nothing about it can be verified from this development environment, which
cannot reach `*.up.railway.app` (same restriction noted throughout this file), so:

**After setting it, smoke-check one real message.** Sign in as a member on the live URL,
send one message to either assistant, and confirm a real reply comes back rather than the
"assistant is unavailable" state. That one round trip exercises the whole path — key,
client wrapper, context assembly, structured output — and is the only way to know the key
is actually live. Same class of gap as the media volume's first real photo upload above.

The **GitHub Actions secret of the same name** is separate and also not set. It is what the
`ai-eval` workflow needs to run the golden set against real Claude; without it that job
exits 1 with a clear message. The eval job never runs on an ordinary push anyway
(decision 32), so this blocks nothing until someone dispatches it or opens a PR touching
the AI layer.

### Before a real gym uses this: the seed is destructive by default

`scripts/seed.py` opens by deleting the gym, and `gyms.id` cascades to every
gym-scoped table. Since it runs as the **Pre-Deploy Command on every deploy**, that
combination would destroy every real member, payment, logged set and photo each time you
shipped — and then re-insert the six invented sales-demo members (Rami Haddad and friends,
some deliberately lapsed to make the "stopped coming" list look good in a demo).

Two defences now, deliberately independent of each other:

- **`--no-demo`** bootstraps a gym's configuration — plans, coaches, machines, exercises,
  classes, the owner account — *inserting only what is absent, never updating*, and never
  deleting the gym. It also clears the demo members if a previous demo seed left them
  behind. `main()` picks this automatically when `AIGYM_ENV=production`.
- **A refusal that does not trust that env var.** If the demo path finds a member on the
  database that it did not invent, it raises rather than repaving. A wrong `AIGYM_ENV`, a
  mistyped flag and a hand-run of the script against production are the same accident, and
  all three stop there instead of at a restore-from-backup.

**Insert-if-absent, never update, is the important half.** Plans, exercises and machines
become the gym's own data the moment they open the app. Dues are derived from
`plans.price_usd` and never stored (decision 17), so a seed that re-asserted its own prices
on every deploy would silently undo `set_gym_plans.py` and quietly corrupt every figure
the product is sold on. Note the consequence: **shipping a corrected plan price by editing
`PLAN_ROWS` no longer works in production** — that is now the gym's data, not the seed's.

**Going live with a real gym, in order:**

```bash
# 1. Confirm the service is marked production (the automatic --no-demo default).
railway variables -s api | grep AIGYM_ENV        # expect: production

# 2. Belt and braces: make the Pre-Deploy Command explicit rather than inferred.
#    sh -c "bash scripts/bootstrap_db.sh && alembic upgrade head \
#           && uv run python scripts/seed.py --no-demo"
#    Remember this only takes effect on a real git push, not a redeploy.

# 3. Set the owner's password (prompts; nothing lands in shell history).
railway ssh -s api -- uv run python scripts/set_staff_password.py

# 4. Set the gym's real prices. The starter $30/$80/$280 are placeholders.
railway ssh -s api -- uv run python scripts/set_gym_plans.py
```

Step 4 is not cosmetic. Every dues figure — what a member owes, what the gym is owed, the
collection rate on the owner dashboard — is computed from these values, so wrong prices do
not look wrong, they just make every downstream number wrong.

### Seeding real content, and setting the manager's password

`scripts/bootstrap_db.sh`, `alembic upgrade head`, and `scripts/seed.py` all run automatically
on every `api` deploy, chained as the service's Railway **Pre-Deploy Command**:

```
sh -c "bash scripts/bootstrap_db.sh && alembic upgrade head && uv run python scripts/seed.py"
```

The `sh -c "..."` wrapper is load-bearing, not decoration — see "Two more real bugs this
surfaced" below for what happens without it. `seed.py` is idempotent — deletes and
re-inserts by fixed id — so this costs nothing on a deploy where the seed data hasn't
changed, and it's what makes editing the seed data (a new class time, a corrected plan
price) ship the same way as any other code change, with no manual step after merging.
There is no separate GitHub Actions job for this: GitHub Actions runs the test suite
(including running `seed.py` against a throwaway CI database, to prove the script itself
works) as the merge gate; Railway's Pre-Deploy Command is what actually migrates and seeds
the one database that matters, right before the new container starts serving.

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

### Two more real bugs this surfaced, both confirmed and fixed

**A multi-command Pre-Deploy Command needs an explicit shell.** The first attempt set it to
the bare chain — `"bash scripts/bootstrap_db.sh && alembic upgrade head && uv run python
scripts/seed.py"` as one array entry. That deployed as `SUCCESS` and looked fine, but
`kassem`'s account stayed broken: `alembic` and `seed.py` never actually ran. Railway execs
each Pre-Deploy Command array entry directly, not through a shell, so the bare `&&` chain was
passed to `bash scripts/bootstrap_db.sh` as **literal trailing arguments** — which it silently
ignores (it takes none), so it ran fine, exited 0, and everything after the first `&&` never
executed at all. No error, no failed deployment, just silence — the exact kind of bug that
looks like success. Fixed by wrapping the whole chain as one shell invocation:
`sh -c "bash scripts/bootstrap_db.sh && alembic upgrade head && uv run python scripts/seed.py"`.

**`redeploy` does not pick up Pre-Deploy Command (or other service config) changes.** Proven
directly: with the config set to just `"alembic upgrade head"` — no reference to
`bootstrap_db.sh` at all — a `redeploy` call still produced `bootstrap_db.sh`'s own output in
the logs. The only explanation is that `redeploy` replays whatever was captured at the
original image's build time, regardless of subsequent `update-service` calls; a Railway
dashboard variable change behaves the same way. The only way to make a Pre-Deploy Command
change (or most other service config changes) actually take effect is a deployment triggered
by a **real git push** — a genuine new build. This cost real time and several confusing
"successful" deploys that changed nothing before it was diagnosed; if this area needs
touching again, change the config, then push a trivial real commit to prove it, don't trust
`redeploy` or a variable-triggered restart to test it.

### What cannot be verified from this environment

`*.up.railway.app` is unreachable from this sandbox (`connect_rejected` on CONNECT) — the
same restriction that already applies to `web`. What *is* verified: the build succeeds,
`scripts/bootstrap_db.sh`, all migrations, and `seed.py` all run cleanly in that exact order
when run locally end-to-end against a real (emptied) local Postgres, and Railway's own
healthcheck probe got `GET /health` → `200 OK` from inside Railway's network on prior
deploys — confirmed via the Railway MCP tools rather than a direct request from here. A
request from outside Railway's network (a phone, a browser with real internet) is still the
one check this environment cannot do itself, same as `web`'s own deploys.
