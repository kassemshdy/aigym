# Data model

Target shape for Phase 2. Phase 1 mirrors a subset in `apps/web/src/mocks/types.ts`.

| Domain | Tables |
|---|---|
| Tenancy | `gyms`, `gym_settings`, `users`, `gym_members` |
| Money | `membership_plans`, `subscriptions`, `payments`, `payment_reminders` |
| Floor | `check_ins`, `workout_sessions`, `session_sets` |
| Programming | `exercises`, `workout_plans`, `plan_days`, `plan_exercises` |
| Member data | `body_metrics`, `lifestyle_profiles`, `nutrition_logs` |
| Content | `videos`, `video_views` |
| Member self-service | `food_entries`, `progress_photos`, `agent_conversations`, `agent_messages` |
| AI | `ai_generations`, `ai_plan_drafts`, `ai_recommendations`, `ai_feedback` |
| Ops | `audit_log` |

## Identity and tenancy

`users` is global identity (phone-first; email optional — most Lebanese gym members do not
use email). `gym_members` joins a user to a gym with a role, so one person can be a coach
at one gym and a member at another.

Roles: `platform_admin` → `gym_owner` → `manager` → `coach` → `member`.

Every tenant table carries `gym_id`, enforced in the service layer and again by Postgres
RLS via `SET LOCAL app.current_gym_id` per request.

## Columns that carry a decision

- **`subscriptions.status` is derived, never stored.** `active` / `expiring_soon` /
  `overdue` is computed from `end_date` and the latest `payments` row, in one service
  function. Two copies of this logic is how a member gets turned away at the door by
  mistake.
- **`payments.amount_usd NUMERIC(10,2)`** — single currency, no rate column.
- **`nutrition_logs.source`** distinguishes `member_logged` from `coach_asked`, so the
  coach's floor conversation is first-class data rather than a note. `calorie_band` stores
  the tapped range; an exact number is optional and rarely present.
- **`videos.provider` + `videos.external_id`** keep the unlisted-YouTube decision
  reversible.
- **`ai_generations`** stores model, prompt version, input snapshot, raw output, tokens,
  and cost. This table *is* the AI observability trail.
- **`idempotency_key` on every write-side table** — required for offline replay. See
  `.agents/skills/offline-sync`.

## Member self-service (added with the member app)

- **`food_entries`** — one row per logged meal: `kcal`, `protein`, `carbs`, `fat`,
  `source` (`photo` / `manual` / `agent`), optional `photo_key`, and for photo entries the
  model's original estimate alongside the member's correction. That pair is the feedback
  signal for improving estimates; drop it and every correction is thrown away.
- **`progress_photos`** — `shared_with_coach BOOLEAN NOT NULL DEFAULT false`. The default
  is part of the schema, not the application, so no code path can accidentally invert it.
  Deletion removes the object from storage, not just the row. See decision 11.
- **`agent_conversations` / `agent_messages`** — one conversation per member per agent
  (`nutrition` / `training`). Messages store role, text, the model and prompt version that
  produced an agent turn, and a nullable `escalated_draft_id` pointing at the
  `ai_plan_drafts` row the turn created. That column is the audit trail proving the agent
  escalated rather than acted.
