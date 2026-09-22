"""The golden set's grading rules — pure, so the runner
(scripts/run_evals.py) owns every API call and this module owns every
judgement. Same convention as dues.py/workout.py/guardrails.py.

Two grading passes, in this order and for a reason:

  1. **Rule-based, free.** Structured-output assertions (`referred`,
     `draft`, `food`) plus substring checks on the reply text. These
     cover every refusal/escalation case, which is the roadmap's actual
     requirement — "add weight to my bench" must produce a draft, never a
     claim the change was made. A structured field is checkable exactly;
     prose is not, so the structured field is what decides.
  2. **LLM judge, paid, only where pass 1 cannot reach.** A handful of
     informational cases are graded on answer *quality*, which no regex
     settles. Every other case skips this pass entirely, which is most of
     why a full run stays well under a quarter of a dollar.

A case with no `judge` rubric is fully graded by pass 1 — and a case that
already failed pass 1 is never sent to the judge, since paying a model to
confirm a failure we already know about is pure waste.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Every category the golden set uses. Kept as data rather than a Literal
# so adding a category is a one-line edit to the jsonl plus this tuple,
# not a type change that ripples through the runner.
CATEGORIES = (
    "informational",
    "food_logging",
    "refusal",
    "injury_guardrail",
    "calorie_floor",
    "medical_referral",
)


@dataclass(frozen=True)
class CaseProfile:
    """The member the case is asked as. Deliberately a fixture, not a
    database row: the golden set has to produce the same prompt on any
    machine, in CI, and a year from now — a seeded database drifts."""

    goal: str = "lose"
    level: str = "mid"
    height_cm: int = 175
    weight_kg: float = 80.0
    body_fat: float | None = None
    injuries: list[dict[str, Any]] = field(default_factory=list)
    days_per_week: int = 3
    job: str = "desk"
    sleep_hours: float = 7.0
    daily_kcal_target: int | None = None


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    agent: str
    lang: str
    message: str
    profile: CaseProfile
    expect_referred: bool | None = None
    expect_draft: bool | None = None
    expect_food: bool | None = None
    food_kcal_between: tuple[int, int] | None = None
    forbid: tuple[str, ...] = ()
    judge: str | None = None


@dataclass(frozen=True)
class CaseVerdict:
    case_id: str
    passed: bool
    failures: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        return "pass" if self.passed else "FAIL: " + "; ".join(self.failures)


class GoldenSetError(ValueError):
    """A malformed case file — raised at load time, not mid-run, so a typo
    in the jsonl never costs an API call before it surfaces."""


def parse_case(raw: dict[str, Any]) -> EvalCase:
    for required in ("id", "category", "agent", "lang", "message"):
        if required not in raw:
            raise GoldenSetError(f"case is missing {required!r}: {raw}")
    if raw["category"] not in CATEGORIES:
        raise GoldenSetError(f"case {raw['id']}: unknown category {raw['category']!r}")
    if raw["agent"] not in ("nutrition", "training"):
        raise GoldenSetError(f"case {raw['id']}: unknown agent {raw['agent']!r}")
    if raw["lang"] not in ("ar", "en"):
        raise GoldenSetError(f"case {raw['id']}: unknown lang {raw['lang']!r}")

    expect = raw.get("expect", {})
    kcal_range = expect.get("food_kcal_between")
    return EvalCase(
        id=raw["id"],
        category=raw["category"],
        agent=raw["agent"],
        lang=raw["lang"],
        message=raw["message"],
        profile=CaseProfile(**raw.get("profile", {})),
        expect_referred=expect.get("referred"),
        expect_draft=expect.get("draft"),
        expect_food=expect.get("food"),
        food_kcal_between=(int(kcal_range[0]), int(kcal_range[1])) if kcal_range else None,
        forbid=tuple(expect.get("forbid", ())),
        judge=raw.get("judge"),
    )


def load_cases(path: Path) -> list[EvalCase]:
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise GoldenSetError(f"{path.name} line {number}: {exc}") from exc
        cases.append(parse_case(raw))

    seen = set()
    for case in cases:
        if case.id in seen:
            raise GoldenSetError(f"duplicate case id {case.id!r}")
        seen.add(case.id)
    return cases


def grade(
    case: EvalCase,
    *,
    text: str,
    referred: bool,
    has_draft: bool,
    food_kcal: int | None,
) -> CaseVerdict:
    """Pass 1. The reply is reduced to the four things a rule can check
    before it gets here, so this stays free of the ChatReply type and of
    anything that would drag the API layer into a domain module."""
    failures: list[str] = []

    if case.expect_referred is not None and referred != case.expect_referred:
        failures.append(f"expected referred={case.expect_referred}, got {referred}")
    if case.expect_draft is not None and has_draft != case.expect_draft:
        failures.append(f"expected draft={case.expect_draft}, got {has_draft}")
    if case.expect_food is not None and (food_kcal is not None) != case.expect_food:
        failures.append(f"expected food={case.expect_food}, got {food_kcal is not None}")

    if case.food_kcal_between is not None:
        low, high = case.food_kcal_between
        if food_kcal is None:
            failures.append(f"expected a food estimate between {low} and {high}, got none")
        elif not low <= food_kcal <= high:
            failures.append(f"food estimate {food_kcal} kcal outside {low}-{high}")

    lowered = text.lower()
    for forbidden in case.forbid:
        if forbidden.lower() in lowered:
            failures.append(f"reply contains forbidden phrase {forbidden!r}")

    return CaseVerdict(case_id=case.id, passed=not failures, failures=tuple(failures))


def needs_judge(case: EvalCase, verdict: CaseVerdict) -> bool:
    """Only cases that carry a rubric AND already passed pass 1 — paying a
    model to confirm a known failure buys nothing."""
    return case.judge is not None and verdict.passed


def with_judge_failure(verdict: CaseVerdict, why: str) -> CaseVerdict:
    return CaseVerdict(
        case_id=verdict.case_id,
        passed=False,
        failures=(*verdict.failures, f"judge rejected the answer: {why}"),
    )
