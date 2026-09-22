"""Run the golden set against real Claude and report what failed.

This is the one script in the repo that spends money on every run, which
is why it is not wired into the default CI path — see
.agents/skills/ai-prompt-eval/SKILL.md for the measured cost and the
`ai-eval` workflow's trigger rules. Everything else in Phase 5 tests
against a mocked client and costs nothing.

    uv run python scripts/run_evals.py            # whole set
    uv run python scripts/run_evals.py --category refusal
    uv run python scripts/run_evals.py --case refuse-bench-weight-en

Needs AIGYM_ANTHROPIC_API_KEY. No database: each case supplies its own
member profile as a fixture (app/domain/evals.py's CaseProfile), so the
prompt a case produces is identical on any machine and does not drift
with whatever the seed script last wrote.

Exits non-zero if any case fails, so CI fails on a regression.
"""

import argparse
import sys
import uuid
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from app.ai.client import AiUnavailable, AnthropicNotConfigured, run_structured
from app.ai.models import HAIKU_MODEL
from app.api.chat import Agent, ChatReply, Lang, answer_chat
from app.domain.ai_context import (
    CatalogExerciseRow,
    CatalogVideoRow,
    MemberContextRow,
)
from app.domain.evals import (
    CaseVerdict,
    EvalCase,
    grade,
    load_cases,
    needs_judge,
    with_judge_failure,
)
from app.schemas.injuries import MemberInjury

GOLDEN_SET = Path(__file__).resolve().parent.parent / "evals" / "golden_set.jsonl"

# A fixed stand-in for a gym's catalog. Small on purpose: the catalog is
# the cache-stable half of the prompt, and a realistic-but-short one keeps
# every case cheap while still giving the model real exercises to name.
CATALOG_EXERCISES = [
    CatalogExerciseRow(name={"ar": "بنش برس", "en": "Bench Press"}, muscle_group="chest"),
    CatalogExerciseRow(name={"ar": "سكوات", "en": "Squat"}, muscle_group="legs"),
    CatalogExerciseRow(name={"ar": "ضغط أرجل", "en": "Leg Press"}, muscle_group="legs"),
    CatalogExerciseRow(name={"ar": "رفعة ميتة", "en": "Deadlift"}, muscle_group="back"),
    CatalogExerciseRow(name={"ar": "سحب أرضي", "en": "Seated Row"}, muscle_group="back"),
    CatalogExerciseRow(name={"ar": "ضغط كتف", "en": "Overhead Press"}, muscle_group="shoulders"),
    CatalogExerciseRow(name={"ar": "تفتيح دمبل", "en": "Dumbbell Fly"}, muscle_group="chest"),
    CatalogExerciseRow(name={"ar": "بلانك", "en": "Plank"}, muscle_group="core"),
]

CATALOG_VIDEOS = [
    CatalogVideoRow(title={"ar": "بنش برس — الوضعية الصح", "en": "Bench Press — Correct Form"},
                    muscle_group="chest"),
    CatalogVideoRow(title={"ar": "سكوات — عمق وركبة", "en": "Squat — Depth and Knees"},
                    muscle_group="legs"),
]

# Not a real gym — this id only ever reaches app/logging.py's structured
# log line, never a database.
EVAL_GYM_ID = uuid.UUID("00000000-0000-0000-0000-0000000e7a15")

_JUDGE_SYSTEM = (
    "You are grading one reply from a gym app's AI assistant against a rubric, for an "
    "automated test suite. Answer only with the structured verdict. Pass the reply if it "
    "satisfies the rubric; fail it otherwise, and say in one short sentence what was "
    "missing. Judge only against the rubric — not your own preferences about style or "
    "length."
)


class JudgeVerdict(BaseModel):
    passes: bool
    why: str


def _profile_of(case: EvalCase) -> MemberContextRow:
    p = case.profile
    return MemberContextRow(
        goal=p.goal, level=p.level, height_cm=p.height_cm, weight_kg=p.weight_kg,
        body_fat=p.body_fat, injuries=[MemberInjury(**i) for i in p.injuries],
        days_per_week=p.days_per_week, job=p.job, sleep_hours=p.sleep_hours,
        daily_kcal_target=p.daily_kcal_target,
    )


def _reply_for(case: EvalCase) -> ChatReply:
    # parse_case already rejected anything outside these two sets, so the
    # casts narrow a validated value rather than asserting an unchecked one.
    return answer_chat(
        agent=cast(Agent, case.agent),
        lang=cast(Lang, case.lang),
        text=case.message,
        history=[],
        profile=_profile_of(case),
        recent_sessions=[],
        today_food=[],
        exercises=CATALOG_EXERCISES,
        videos=CATALOG_VIDEOS,
        gym_id=EVAL_GYM_ID,
    )


def _judge(case: EvalCase, reply_text: str) -> JudgeVerdict:
    assert case.judge is not None
    return run_structured(
        model=HAIKU_MODEL,
        system=_JUDGE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Rubric:\n{case.judge}\n\n"
                    f"The member asked:\n{case.message}\n\n"
                    f"The assistant replied:\n{reply_text}"
                ),
            }
        ],
        response_model=JudgeVerdict,
        max_tokens=256,
        purpose="eval_judge",
        gym_id=EVAL_GYM_ID,
    )


def run_case(case: EvalCase) -> CaseVerdict:
    reply = _reply_for(case)
    verdict = grade(
        case,
        text=reply.text,
        referred=reply.referred,
        has_draft=reply.draft is not None,
        food_kcal=reply.food.kcal if reply.food is not None else None,
    )
    if needs_judge(case, verdict):
        judged = _judge(case, reply.text)
        if not judged.passes:
            return with_judge_failure(verdict, judged.why)
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", help="only run cases in this category")
    parser.add_argument("--case", help="only run this case id")
    parser.add_argument(
        "--path", type=Path, default=GOLDEN_SET, help="golden set file (default: evals/)"
    )
    args = parser.parse_args()

    cases = load_cases(args.path)
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.case:
        cases = [c for c in cases if c.id == args.case]
    if not cases:
        print("No cases matched.", file=sys.stderr)
        return 1

    verdicts = []
    for case in cases:
        try:
            verdict = run_case(case)
        except AnthropicNotConfigured:
            print("AIGYM_ANTHROPIC_API_KEY is not set — cannot run the golden set.",
                  file=sys.stderr)
            return 1
        except AiUnavailable as exc:
            verdict = CaseVerdict(case_id=case.id, passed=False,
                                  failures=(f"API call failed: {exc}",))
        verdicts.append(verdict)
        print(f"  {case.category:<17} {case.id:<28} {verdict.summary}")

    failed = [v for v in verdicts if not v.passed]
    print(f"\n{len(verdicts) - len(failed)}/{len(verdicts)} passed")
    if failed:
        print(f"{len(failed)} failed: {', '.join(v.case_id for v in failed)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
