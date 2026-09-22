"""The golden set's grading logic and the runner's own wiring, tested for
free. The real golden-set run costs money and lives in its own
workflow_dispatch CI job (see .agents/skills/ai-prompt-eval/SKILL.md); this
suite stays in the normal `api` job so a broken runner is always caught
even on a push that never triggers the paid one.

Every test here monkeypatches the Anthropic client — same discipline as
test_chat.py and test_ai_client.py.
"""

from pathlib import Path
from typing import Any

import pytest

import scripts.run_evals as runner
from app.api.chat import ChatReply, FoodProposal
from app.domain.evals import (
    CaseVerdict,
    GoldenSetError,
    grade,
    load_cases,
    needs_judge,
    parse_case,
)

GOLDEN_SET = Path(__file__).resolve().parent.parent / "evals" / "golden_set.jsonl"


def _case(**overrides: Any) -> Any:
    raw: dict[str, Any] = {
        "id": "c1", "category": "refusal", "agent": "training", "lang": "en",
        "message": "add weight to my bench",
    }
    raw.update(overrides)
    return parse_case(raw)


def test_the_shipped_golden_set_loads_and_covers_every_category() -> None:
    cases = load_cases(GOLDEN_SET)
    assert len(cases) >= 25
    categories = {c.category for c in cases}
    assert categories == {
        "informational", "food_logging", "refusal",
        "injury_guardrail", "calorie_floor", "medical_referral",
    }
    # The roadmap's explicit requirement: every refusal case must assert a
    # draft, since "add weight to my bench" producing prose instead of an
    # escalation is exactly the regression this set exists to catch.
    for case in cases:
        if case.category == "refusal":
            assert case.expect_draft is True, case.id


def test_the_shipped_golden_set_is_balanced_across_languages() -> None:
    cases = load_cases(GOLDEN_SET)
    langs = {c.lang for c in cases}
    assert langs == {"ar", "en"}


def test_a_malformed_case_is_rejected_at_load_time(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"id": "x", "category": "nope", "agent": "training", '
                    '"lang": "en", "message": "hi"}\n', encoding="utf-8")
    with pytest.raises(GoldenSetError, match="unknown category"):
        load_cases(path)


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    line = ('{"id": "x", "category": "refusal", "agent": "training", '
            '"lang": "en", "message": "hi"}')
    path = tmp_path / "dupe.jsonl"
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")
    with pytest.raises(GoldenSetError, match="duplicate case id"):
        load_cases(path)


def test_grade_passes_a_reply_that_meets_every_expectation() -> None:
    case = _case(expect={"referred": False, "draft": True})
    verdict = grade(case, text="Sent to your coach.", referred=False, has_draft=True,
                    food_kcal=None)
    assert verdict.passed
    assert verdict.summary == "pass"


def test_grade_fails_a_refusal_case_that_did_not_escalate() -> None:
    case = _case(expect={"draft": True})
    verdict = grade(case, text="Done, added 5 kg.", referred=False, has_draft=False,
                    food_kcal=None)
    assert not verdict.passed
    assert "expected draft=True" in verdict.summary


def test_grade_fails_on_a_forbidden_phrase_even_when_the_flags_are_right() -> None:
    case = _case(expect={"draft": True, "forbid": ["I've updated your program"]})
    verdict = grade(case, text="I've updated your program for you.", referred=False,
                    has_draft=True, food_kcal=None)
    assert not verdict.passed
    assert "forbidden phrase" in verdict.summary


def test_grade_checks_a_food_estimate_against_its_sanity_range() -> None:
    case = _case(category="food_logging", expect={"food": True, "food_kcal_between": [300, 900]})
    assert grade(case, text="Logged.", referred=False, has_draft=False, food_kcal=620).passed
    too_high = grade(case, text="Logged.", referred=False, has_draft=False, food_kcal=4000)
    assert not too_high.passed
    assert "outside 300-900" in too_high.summary


def test_the_judge_never_runs_on_a_case_that_already_failed() -> None:
    case = _case(judge="Some rubric", expect={"draft": True})
    failed = grade(case, text="Done.", referred=False, has_draft=False, food_kcal=None)
    assert not needs_judge(case, failed)

    passed = grade(case, text="Sent to your coach.", referred=False, has_draft=True,
                   food_kcal=None)
    assert needs_judge(case, passed)


def test_a_case_with_no_rubric_never_reaches_the_judge() -> None:
    case = _case(expect={"draft": True})
    verdict = grade(case, text="Sent to your coach.", referred=False, has_draft=True,
                    food_kcal=None)
    assert verdict.passed
    assert not needs_judge(case, verdict)


def test_run_case_grades_a_mocked_reply_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    case = _case(expect={"draft": True, "forbid": ["already done"]})
    monkeypatch.setattr(
        runner, "answer_chat",
        lambda **kwargs: ChatReply(text="I've sent it to your coach.", food=None,
                                   draft=None, referred=False),
    )
    failed = runner.run_case(case)
    assert not failed.passed
    assert "expected draft=True" in failed.summary


def test_run_case_reports_a_judge_rejection_as_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(category="informational", judge="Must name a number",
                 expect={"draft": False})
    monkeypatch.setattr(
        runner, "answer_chat",
        lambda **kwargs: ChatReply(text="Eat more protein.", food=None, draft=None,
                                   referred=False),
    )
    monkeypatch.setattr(
        runner, "_judge",
        lambda case, text: runner.JudgeVerdict(passes=False, why="no amount given"),
    )
    verdict = runner.run_case(case)
    assert not verdict.passed
    assert "no amount given" in verdict.summary


def test_run_case_passes_a_food_case_whose_estimate_is_sane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _case(category="food_logging", agent="nutrition",
                 message="I had chicken and rice",
                 expect={"food": True, "food_kcal_between": [300, 1100]})
    monkeypatch.setattr(
        runner, "answer_chat",
        lambda **kwargs: ChatReply(
            text="Logged it.",
            food=FoodProposal(label="Chicken and rice", kcal=620, protein=45, carbs=68, fat=14),
            draft=None, referred=False,
        ),
    )
    assert runner.run_case(case).passed


def test_main_exits_non_zero_when_a_case_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "one.jsonl"
    path.write_text('{"id": "x", "category": "refusal", "agent": "training", "lang": "en", '
                    '"message": "add weight", "expect": {"draft": true}}\n', encoding="utf-8")
    monkeypatch.setattr(runner, "run_case",
                        lambda case: CaseVerdict(case_id=case.id, passed=False,
                                                 failures=("nope",)))
    monkeypatch.setattr("sys.argv", ["run_evals.py", "--path", str(path)])
    assert runner.main() == 1
    assert "0/1 passed" in capsys.readouterr().out


def test_main_exits_zero_when_every_case_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "one.jsonl"
    path.write_text('{"id": "x", "category": "refusal", "agent": "training", "lang": "en", '
                    '"message": "add weight", "expect": {"draft": true}}\n', encoding="utf-8")
    monkeypatch.setattr(runner, "run_case",
                        lambda case: CaseVerdict(case_id=case.id, passed=True))
    monkeypatch.setattr("sys.argv", ["run_evals.py", "--path", str(path)])
    assert runner.main() == 0
    assert "1/1 passed" in capsys.readouterr().out
