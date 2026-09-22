---
name: ai-prompt-eval
description: Changing a prompt, a guardrail, or anything under app/ai/. The golden set is how you find out whether the change broke the assistants.
---

# The golden set

```bash
cd apps/api
uv run python scripts/run_evals.py              # whole set, needs the API key
uv run python scripts/run_evals.py --category refusal
uv run python scripts/run_evals.py --case refuse-bench-weight-en
```

`apps/api/evals/golden_set.jsonl` — one JSON object per line, `//` lines are comments.
The runner grades `answer_chat()` from `app/api/chat.py`, which is the same function the
live route calls. That is deliberate: an eval that exercises a copy of the prompt measures
the copy, not the product.

No database is involved. Each case carries its own member profile as a fixture, so the
prompt a case produces is identical on your machine, in CI, and a year from now — a seeded
database drifts, and a drifting fixture turns a red eval into a shrug.

## What a run costs

**Under $0.25 for the full set.** Roughly 25 short Haiku calls plus a judge call on the
handful of cases that carry a rubric, against Haiku's $1/$5 per-MTok pricing with the
catalog half of the prompt cached. Two of the cases — the medical referrals — cost exactly
nothing, because the deterministic pre-filter answers them before any request is made.

That number is why the eval is not in the default CI path (decision 32). Do not re-derive
it from scratch every time someone asks; re-measure it only if the set grows a lot or the
model changes.

## When CI runs it

`.github/workflows/ai-eval.yml`, on `workflow_dispatch` and on pull requests that touch
`app/ai/**`, `app/api/chat.py`, `app/domain/guardrails.py`, `app/domain/ai_context.py`,
`app/domain/evals.py`, `evals/**`, or the runner. **Never on every push** — a
money-spending job on a path everyone hits is a bill nobody agreed to.

It needs the `AIGYM_ANTHROPIC_API_KEY` repository secret (same value as the Railway `api`
service's). Without it the runner exits 1 with a plain message rather than failing
somewhere inside the SDK.

`tests/test_evals.py` is the free half and lives in the normal `api` job: it proves the
grader and the runner's wiring still work, using a mocked client. A broken runner is
always caught, even on a push that never triggers the paid job.

## Grading, in two passes

1. **Rule-based, free.** Assertions on the *structured* output — `referred`, `draft`,
   `food`, a sanity range on a food estimate — plus forbidden-substring checks on the
   reply text. A structured field is checkable exactly; prose is not, so the structured
   field is what decides.
2. **LLM judge, paid.** Only for cases that carry a `judge` rubric, and only if they
   already passed pass 1. Paying a model to confirm a failure you already know about buys
   nothing.

Grading logic lives in `app/domain/evals.py` and is pure — it never sees a `ChatReply` or
an HTTP layer, which is what makes it testable for free.

## What counts as a refusal case here

Not "the model said no." A refusal case passes when the request to change a program or a
calorie target came back as **`draft: true`** — a real row in the coach's inbox — and the
reply text does **not** claim the change was already made. Decision 10 is a property of
the structured output, never of the prose, so that is what the case asserts. Every
`refusal` case in the set asserts `draft: true`; `tests/test_evals.py` enforces that, so a
new case cannot quietly be added without it.

The forbidden phrases matter as much as the flag. A reply that escalates correctly *and*
tells the member "I've updated your program" has still broken the promise the product
makes, so both languages' versions of that claim are listed in the case's `forbid`.

## Adding a case

Append a line to the jsonl. Keep both languages represented — an assistant that only
behaves in English is broken (constraint 5). Fields:

- `id`, `category`, `agent` (`nutrition`/`training`), `lang` (`ar`/`en`), `message`
- `profile` — optional, overrides any of `CaseProfile`'s defaults (goal, weight, injuries…)
- `expect` — `referred`, `draft`, `food`, `food_kcal_between`, `forbid`
- `judge` — optional rubric, in English, for the answer-quality pass

A malformed case is rejected at load time, before any API call, so a typo costs nothing.

Prefer a rule over a rubric. Every rubric you add is a paid call on every future run, and
a rule is both free and unambiguous — reach for `judge` only when the thing you care about
genuinely is the quality of the prose.

## When a case fails

Read what it asserted before touching the prompt. A failing refusal case is a real
regression in the product's core promise and is never "the model being chatty." A failing
rubric case may instead be a rubric that was always too strict — but decide that by
reading the reply the runner printed, not by loosening the rubric until it passes.
