# Decisions

Each entry is a decision that is expensive to reverse, with the reason and the cost of
being wrong. Add to it rather than rewriting history.

## 1. Lebanon is the target market

Everything else follows from this. Lebanese gyms run through power cuts, on patchy
internet, on mid-range Android phones, in Arabic, and their real alternative to this
product is a WhatsApp group and a paper notebook — not Trainerize at $248/month.

## 2. USD only

Plans, payments, and reports are one currency. No exchange-rate field, no dual display, no
re-pricing as a rate moves, no conversion bugs.

*Cost if wrong:* adding LBP later means a currency column on `payments` and a per-gym rate
table. Contained, because money is only formatted in one place (`lib/format.ts`).

## 3. Membership payments are tracked, not processed

The manager marks paid/unpaid. No cards, no PCI scope, no processor account.

*Open question for Phase 6:* billing gym owners for the SaaS itself. Stripe does not
support Lebanese businesses, so the realistic options are collecting via Whish/OMT/bank
transfer and marking gyms paid manually, or incorporating elsewhere. Nothing in Phases 1–5
may assume a card is on file.

## 4. WhatsApp deep links, sent by a human

The app composes an Arabic message and opens `wa.me`; a person taps send. No Business API,
no template approval, no per-message cost, and the gym's number does not get reported for
automated blasts. Automation is a Phase 6 question, only if gyms ask for it.

## 5. Video is unlisted YouTube/Vimeo embeds

Zero hosting cost, zero transcoding, works on day one.

**Known limitation, stated plainly:** an unlisted link is not access control. Anyone who
gets the link can watch forever, including ex-members. `videos.provider` +
`videos.external_id` keep this reversible — moving to Cloudflare Stream with signed URLs
is a provider change, not a rewrite.

## 6. FastAPI + React, not Next.js

Python backend for the AI layer, React SPA frontend, deployed as separate Railway
services. Explicitly chosen over Next.js.

## 7. Multi-tenant from day one, defended twice

Every tenant table carries `gym_id`, enforced in the service layer **and** by Postgres
Row-Level Security. A service-layer bug then returns an empty set instead of leaking
another gym's members. This is the highest-stakes correctness property in the product and
it gets its own test job in CI.

## 8. 200 KB gzipped JS budget

Enforced in CI. Raising it requires an entry in this file saying what users get in
exchange. This is why there is no charting library — `Sparkline` is hand-written SVG.

## 9. Agent tooling follows Sentry's layout

`AGENTS.md` is the source of truth, `CLAUDE.md` is a one-line pointer to it, skills live in
`.agents/skills/` with `.claude/skills` symlinked to that directory.

## 10. Chat agents answer and log, but never change the program

Two assistants the member can talk to: a **nutrition assistant** and a **bodybuilding
assistant**. Both answer freely and may log food the member reports. Neither can change
the training program or the calorie targets — a request like "add weight to my bench"
becomes a pending draft in the coach's inbox, and the member is told so in the reply.

This keeps the approval rule that already governs generated plans: nothing reaches a
member's body without a human coach seeing it. It also protects the coach's relationship
with their own clients — an assistant that quietly rewrites a program is competing with
the coach, not helping them.

*Enforced in code, not in the prompt.* The reply carries a `draft` flag and the store
routes it to the coach; the model is never the thing standing between a suggestion and the
member's program.

## 11. Progress photos are private by default

Members can add progress photos. Three rules, none of them opt-out:

1. **Private by default** — `shared_with_coach` starts false, always.
2. **Sharing is per-photo and explicit** — a separate confirm step, never a blanket
   setting, never a consequence of joining a gym.
3. **Delete really deletes** — including the stored file, not just the row.

Body photos are the most sensitive data in the product. A gym owner or coach browsing
members' bodies because the default allowed it is the kind of harm that ends a product,
and "the member could have turned it off" is not a defence.

Food photos carry none of this weight and are treated as ordinary log data.

## 12. Food photo estimates always get a confirm step

The member photographs a meal, the model estimates it, and **the member confirms or
corrects before anything is logged** — with a portion stepper for the common case where
the food is right and the amount is not.

An estimate that logs itself silently is a number nobody trusts and everybody stops
reading. The confirm step is also the cheapest training signal we will ever get: the
difference between what the model guessed and what the member corrected.

## 13. Member auth is phone + code, no email, no password

Most members here do not use email, and a password is one more thing to forget at the
door. The code goes over WhatsApp, which everyone already has open.

## 14. English is the default language, Arabic is equal

The app opens in English and LTR. Arabic remains fully supported — same key coverage, same
RTL layout rules, same plain-Levantine wording — and the toggle is one tap in the header.

This reverses the earlier Arabic-default choice. Nothing else changed: the RTL checks still
run in CI, seed content is still bilingual `{ ar, en }` pairs, and a layout that only works
in English still fails review. Defaulting to English is a starting point, not a demotion of
Arabic.

## 15. Dockerfile and Caddy on Railway, and no `railway.json`

The web app deploys to Railway as a two-stage Docker build: Node produces `dist/`, Caddy
serves it. No Node process at runtime.

**No `railway.json`.** Railway's Config as Code is deprecated — existing files stop being read
on **2026-12-01**, and new services cannot opt into it at all, so a config file added for this
service would never have been read. Configuration instead lives in the Dockerfile (Railway
always builds with one when it finds one) and in the service's own settings. Infrastructure as
Code (`.railway/railway.ts`) is the supported replacement and is worth adopting in Phase 2,
when there is an API, a worker, Postgres and Redis to describe rather than a single static
service; it needs the Railway CLI and an interactive login, so it runs from a developer
machine.

**The SPA fallback is not optional.** 20 client-side routes means a plain static server 404s
on 19 of them after a refresh or a pasted link — and a link people can open is the entire
reason to deploy. `try_files {path} /index.html` handles it, and it is verified by curling
deep links rather than assumed.

**HTML is never cached, assets always are.** Vite content-hashes `/assets`, so those are
immutable for a year; anything resolving to `index.html` is `no-cache`. Matching that on
`not path /assets/*` rather than the literal `/index.html` is deliberate: the literal form
misses `/` and every deep link, and a stale shell surviving a redeploy points at hashed assets
that no longer exist — a white screen for someone on a bad connection who can least afford to
debug it.

## 16. Row-Level Security is enforced against a role that cannot bypass it

Every gym-scoped table gets `ALTER TABLE … ENABLE ROW LEVEL SECURITY` *and*
`FORCE ROW LEVEL SECURITY`, plus one policy:

```sql
CREATE POLICY tenant_isolation ON members
  USING (gym_id = NULLIF(current_setting('app.gym_id', true), '')::uuid)
  WITH CHECK (gym_id = NULLIF(current_setting('app.gym_id', true), '')::uuid)
```

Two traps this closes, both found by testing the policy itself rather than trusting it:

**The owner-bypass trap.** A table's owner ignores its own RLS policies unless the table is
also `FORCE`d — and Postgres superusers ignore RLS *regardless* of `FORCE`. So migrations run
as the owning role (`AIGYM_DATABASE_URL_MIGRATIONS`), and the API connects as a separate,
non-superuser role (`aigym_app`, `NOBYPASSRLS`) that owns nothing. Testing isolation through
the owner connection would prove nothing; the isolation suite (`tests/test_tenancy_isolation.py`)
deliberately uses `aigym_app`.

**The reset-to-empty-string trap.** `current_setting('app.gym_id', true)` returns `NULL` — safe,
matches no row — when the session has *never* touched `app.gym_id`. But once a transaction
calls `set_config('app.gym_id', …, true)` (the parameterized equivalent of `SET LOCAL`, used so
the value is a bound parameter rather than a string-built statement), Postgres resets the
setting to `''`, not back to `NULL`, once that transaction ends. A pooled connection reused for
a later, unscoped query would then hit `''::uuid`, a hard error, instead of failing closed.
`NULLIF(…, '')` turns both cases into `NULL` before the cast, so "never scoped" and "scoped
earlier, now out of scope" fail the same safe way: zero rows, no exception. Caught by testing
the exact sequence — scope a transaction, commit, query again unscoped, on the real `aigym_app`
role — not by reading the policy and assuming it was right.

`gyms` and `staff_users` are the two tables *without* this policy — a gym cannot scope itself,
and a staff login has to find a `staff_users` row by phone before any gym is known. Every other
gym-scoped table gets it, including auth-adjacent ones like `refresh_tokens`. The one deliberate
further exception is `member_login_codes`: verifying a member's 6-digit code is looked up by
phone alone, before the gym is known, so it is unscoped like `gyms`/`staff_users` rather than
routed through an elevated connection.

## 17. Dues status is computed, never stored

`app/domain/dues.py` is the only place `paid | soon | due` and `owed_usd` are computed, from a
subscription's `ends_at` plus its plan's price and length — never written to a column. Storing
it needs a nightly job and opens a class of bug where the badge and the truth disagree; computing
it on every read costs nothing a gym's data volume will ever notice.

## 18. Staff login resolves gym membership through a second, narrowly-scoped connection

Decision 16 makes `staff_gym_roles` RLS-protected like every other gym-scoped table — but staff
login has to ask "which gym(s) does this already-PIN-verified person belong to" *before* any
`app.gym_id` is known, which is exactly the query that table's own RLS policy exists to block.

Rather than weaken that policy, `app/db.py`'s `get_owner_sessionmaker()` opens a second
connection pool on the migrations/owner role, used from exactly one call site — resolving a
verified staff member's roles at login — and nowhere else. The PIN check happens first, on the
unscoped `staff_users` table (no RLS, decision 16); only after that succeeds does the elevated
read run, and only to answer "which gyms," never to read gym data itself.

## 19. Member login codes are unscoped, not routed through an elevated connection

`member_login_codes` (decision 16) takes the opposite approach from staff login: rather than an
elevated connection, the table itself carries no RLS, the same treatment as `gyms` and
`staff_users`. A verify request supplies only a phone number, so the lookup is
`WHERE phone = :phone AND code_hash = :hash AND expires_at > now() AND used_at IS NULL` with no
gym to scope by — the match itself is what reveals which gym to scope the resulting session to.

This is safe specifically because the code is already hashed, single-use, 5-minute expiry, and
rate-limited per member (decision 13) — the code's own properties are the defense, not table
visibility. An elevated connection would work too, but for a table this narrow and this
purpose-built, a second exception to the RLS-everywhere rule is more honest than laundering the
same access through a connection meant for staff auth.

## 20. Staff password reset is the one WhatsApp message that goes through the real Business API

Decision 4 rules out the WhatsApp Business API everywhere else in this product: a human at the
front desk taps a `wa.me` link, so there's no per-message cost, no Meta template approval, and
no risk of the gym's number getting flagged for automated sends. That reasoning doesn't hold for
`POST /auth/staff/password/reset` — a staff member locked out of their own login has no front
desk to hand a link to, so automated delivery is the actual point, not a convenience.

`app/integrations/whatsapp_business.py` is kept deliberately separate from
`app/domain/whatsapp.py` (the `wa_link` helper decision 4 governs) so the distinction stays
visible in the codebase, not just in a comment. `AIGYM_WHATSAPP_ACCESS_TOKEN` and
`AIGYM_WHATSAPP_PHONE_NUMBER_ID` are both unset by default, so a deployment that hasn't
configured this degrades to "password reset but no message sent" (`{"sent": false}`) rather than
an error — the reset itself never depends on WhatsApp succeeding.

The endpoint takes only a username and no auth — that's what makes it a recovery path at all —
so it's rate-limited via a dedicated `staff_users.password_reset_at` column (NULL until first
use, so a freshly created account's first reset is never blocked by its own creation — reusing
`updated_at` for this was tried first and is exactly wrong for that reason). It's looked up by
username (decision 21's login identifier) but delivered to the phone on file, which still has
to exist on every staff row for exactly this reason even though it's no longer the login
credential. The security model is the same one member login codes already rely on (decision
19): knowing the identifier lets you trigger a reset, but the new password is only ever visible
to whoever actually holds the phone.

## 21. Staff log in with username + password; only super_admin creates staff accounts

Explicit user decision, reversing the phone + PIN login this product shipped Phase 2 with for
staff specifically — **members are unaffected**: they still sign in with phone + a WhatsApp
code (decision 13's reasoning — most members have no email, and this is a market where minimal
typing matters more than most — still holds for them). Only `staff_users` changed.

`username` replaces `phone` as the login identifier; `password_hash` replaces `pin_hash`. Phone
stays on the row — it's no longer how a staff member logs in, but it's still how decision 20's
password-reset delivers a new one, over WhatsApp.

The gym's first account (created by `POST /gyms`) is `super_admin`, not `manager` — it has to
be, or nobody could ever create a second staff account. `POST /staff` is new: it creates
additional staff accounts (managers, coaches, or more super_admins) and is gated to
`super_admin` via `require_role`. That surfaced a real trap worth stating plainly:
`require_role` roles are flat strings, not a hierarchy — `super_admin` does **not** implicitly
satisfy `require_role("manager", "coach")` on every other gated endpoint. Every existing call
site had to be updated to list `super_admin` explicitly (see `app/deps.py`'s `require_role`
docstring), and a new endpoint that forgets to will silently 403 a super_admin instead of
erroring — there is no automated check for this yet.

Migrating `staff_users.username` to `NOT NULL UNIQUE` against a database that already had rows
(this shipped after Triple A Gym's real account existed) needed a hand-written backfill —
autogenerate cannot write one. The migration derives a username from each existing row's phone
digits before adding the constraint; `scripts/seed.py` separately reasserts the friendly
`"kassem"` username on every run regardless of whether the row pre-existed, so the real account
doesn't end up stuck with a digits-only backfilled username. `password_hash` is excluded from
that reassertion — seeding must never touch a credential someone already set.

*Amended by decision 25*: a manager can now create coach accounts too, not just super_admin.

## 22. Workout sessions and sets get client-mintable ids — the one exception to server-minted ids

Every other table in this codebase lets the server generate `id = uuid.uuid4()` on insert.
`workout_sessions` and `workout_sets` (and, for the same reason, `nutrition_logs`) accept an
*optional* client-supplied `id` instead, defaulting to a server-generated one only when the
caller omits it.

The reason is specific to Phase 3's offline outbox: a coach who starts a session while offline
must be able to reference that session's id in the very next queued request — "log a set in
session X" — before either request has ever reached the server. Waiting for a server response to
learn the id would mean the outbox can't be a single ordered queue of independent requests; it
would need a dependency graph instead. A client-generated UUID v4 makes collision astronomically
unlikely and means the id in `src/offline/outbox.ts`'s queued body *is* the real id, not a
placeholder swapped out later — the local echo (`src/data/client.ts`'s `offlineFetch`) and the
eventual server row always agree.

This is deliberately narrow: only the three tables an offline coach actually writes to got this.
Everything else — members, plans, payments, programs — keeps server-minted ids and stays
online-only (decision 23), because nothing about *their* write pattern needs a client-known id
before the round trip completes.

## 23. The offline outbox covers floor writes only, and check-in creation stays online-only

`.agents/skills/offline-sync`'s conflict-rule table names "session data (sets, reps, nutrition
entries)" as client-wins; Phase 3 implements exactly that scope — `workout_sessions`,
`workout_sets`, `nutrition_logs`, and check-in *status* updates (`PATCH /check-ins/{id}`) — and
nothing wider. Member, plan, and payment writes still fail visibly rather than queue, unchanged
from Phase 2. Extending the same mechanism to them later is cheap, since the outbox lives in the
shared `apiFetch`/`offlineFetch` layer in `client.ts`, not duplicated per feature — but it wasn't
needed for what the roadmap's own test method describes ("killing the network mid-session").

**Check-in *creation* (`POST /check-ins`) is the one floor write that stays online-only**, unlike
its sibling status-update endpoint. The reason is decision 22's own logic run in reverse: check-in
ids are always server-minted — `CheckInRequest` has no client-id field — so there is no safe local
echo to hand back if the write is queued. A queued check-in would show the coach an id the real
row will never actually have, and anything built on top of it (a QR receipt, a downstream link)
would silently point at nothing once the real one lands. Front-desk check-in also happens where
connectivity is least likely to be the actual problem — the floor is where it drops, not the
counter — so the cost of staying online-only here is low. `updateCheckInStatus`, by contrast,
targets a check-in id that's already real, so its echo is exact.

## 24. A dependency's real bundle cost has to be measured, not estimated, before it ships

QR-code check-in was planned and approved (a ~5–10 KB pure-JS decoder, since Safari on the coach's
iPad has no `BarcodeDetector`). The actual dependency (`jsqr`) cost **~51 KB gzipped** — enough to
push the total bundle to 179.7 KB against the 200 KB budget (decision 8), with the rest of Phase 3
(the offline outbox, the service worker) still unbuilt and needing headroom. The estimate was
wrong by roughly 5–10x.

Dropped rather than kept: `npm uninstall jsqr`, camera code deleted, manual name-search kept as
the only check-in path. The bundle returned to ~131 KB. QR check-in is not implemented anywhere in
Phase 3 — reconsider only alongside a lighter decoder, or once Phase 4's member-facing QR display
exists to make the trade-off worth relitigating (today, nothing renders a code for the camera to
even scan).

The process lesson, not just the outcome: `npm run build && npm run budget` after adding a
dependency is not optional, and a KB estimate given before installing it is a guess, not a
measurement — decision 8's "raising the budget requires an entry saying what users get in
exchange" cuts the other way here too: a dependency that turns out to cost far more than planned
gets re-evaluated against the same budget, not grandfathered in because it was already approved
under a wrong number.

## 25. A manager can create coach accounts; escalation stays super_admin-only

Amends decision 21. The gym owner asked directly: a manager needs to be able to staff up the
floor — add a coach the day they're hired — without waiting on the one `super_admin` account.
Requiring super_admin for every new hire was the more conservative choice Phase 2 shipped with
by default, not something the owner had actually asked for; once coach screens went live in
Phase 3 and staffing coaches became a real, recurring task, the gap became worth closing.

`POST /staff`'s role gate is now `require_role("super_admin", "manager")`, with the actual
restriction enforced in the handler, not the dependency: a caller whose own role is `manager`
gets a 403 unless `body.role == "coach"`. A manager can never create another manager or a
super_admin through this endpoint — that stays exactly as restrictive as decision 21 originally
made it. `CreateStaffRequest.role` also gained a `Literal["manager", "coach", "super_admin"]`
type, catching a garbage role value at the request-validation layer instead of it reaching the
permission check at all.

`GET /staff` is new alongside it — listing who already has access is what makes the manager's
own new `/manager/staff` screen (the first UI this product has ever had for staff creation; every
account before this, including the ones seeded for Triple A Gym's real coaches, was created by
hand over the API) useful rather than a one-way form. Both endpoints are gated identically
(`super_admin` or `manager`); a coach can reach neither.

**What stays out of scope on purpose:** self-service password reset for a newly created coach
still goes through decision 20's WhatsApp flow, not a new mechanism — the manager sets a
temporary password at creation time, same as before, and the coach can request a real one to
their own phone whenever they first try to sign in. No screen exists yet for a manager to change
an existing coach's role, deactivate one, or reset a coach's password directly — those are real
gaps if a coach ever needs to be let go, not just added, and are worth their own decision if
asked for.

## 26. New coach credentials go out as a wa.me link, not the WhatsApp Business API

A new coach account needs its username and temporary password delivered somewhere. The
obvious automated path — the Meta WhatsApp Business API integration built for decision 20's
password-reset flow — was deliberately not reused here: the owner asked for it not to be,
same reasoning decision 4 already settled for every other WhatsApp message in this product.
No Business API means no per-message cost, no template approval, and no risk of the gym's
number getting flagged for automated sends. A human taps send.

`/manager/staff`'s post-creation screen now shows a `wa.me` link, pre-filled via the same
`waLink()` helper `AddMember.tsx` already uses for the member welcome message — username,
password, and a sign-in link (`window.location.origin + '/staff/login'`, computed at click
time so it's correct on whichever domain the manager is actually using, dev or production).
The manager opens WhatsApp Web or the app and sends it themselves.

This also settles a question decision 20 left open: the Business API credentials
(`whatsapp_access_token`, `whatsapp_phone_number_id`) are not configured on the live `api`
service, and per this decision, configuring them is not planned — decision 20's automated
flow stays scoped to the one thing that actually needs automation (a locked-out coach can't
tap a link a human hands them), and everything else, credentials included, stays a wa.me
link.

## 27. A hand-rolled walkthrough and help tooltips, not a tour library

The gym owner asked for onboarding help for every role — "a manager who has never used
software should need no training" (the product's own third constraint) is a promise, not
just an aspiration, and a first login with no guidance breaks it as much as a confusing
screen would.

Scoped to the two staff surfaces that run on real data today, manager and coach — member
screens are still Phase 4's to build, and polishing an onboarding pass into a screen about to
be rebuilt would be wasted work. Two pieces, both hand-rolled (`src/help/`), no new
dependency — the decision 24 lesson (measure, don't estimate a library's cost) made checking
first the obvious move, and a spotlight-and-tooltip overlay plus a "?" popover are both a
few dozen lines of plain React; a tour library would have cost more of the 200 KB budget than
the feature itself:

- **`TourProvider`** — a short (four-step) guided overlay, auto-started once per role via a
  `localStorage` seen-flag the first time that role's home screen mounts, and replayable
  anytime from a "?" button in the header. Steps target real DOM elements via a
  `data-tour="…"` attribute, measured with `getBoundingClientRect()` — the spotlight ring
  and tooltip bubble both use plain physical `left`/`top` inline styles, which is the correct
  choice here despite the project's own "never a physical-direction utility" rule: that rule
  governs static Tailwind classes that don't respond to `dir`, not JS math against real
  viewport-coordinate measurements, which are dir-agnostic by construction.
- **`HelpTip`** — a small "?" affordance opening a short popover, positioned with the
  logical `end-0` utility (this one *is* static CSS, so the ms-/me- rule applies normally).
  Used sparingly — two placements so far (why a manager can't add another manager on
  `/manager/staff`, what the video-link icon on `ProgramEditor` does) — because most of this
  product already explains itself through plain labels, which is the whole point of "no
  jargon" in the first place; a tooltip on every control would fight that, not support it.

`scripts/shots.mjs` seeds both roles' seen-flags in its init script, the same way it already
seeds `aigym.signedIn` — the screenshot suite captures steady-state screens, not the one-time
onboarding overlay.
