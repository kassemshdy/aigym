"""'Today's workout' and 'last weight for an exercise' are both derived on
read, never stored — same discipline as dues.py. These are pure functions:
the API route queries workout_sets/program_exercises and hands the rows in
here, so the merge logic is testable without a database and this module
stays free of HTTP or SQLAlchemy-session awareness, per apps/api/AGENTS.md.
"""

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProgramExerciseRow:
    id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: dict[str, Any]
    order_index: int
    sets: int
    reps: dict[str, Any]
    target_weight_kg: float | None


@dataclass(frozen=True)
class TodayExercise:
    program_exercise_id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: dict[str, Any]
    order_index: int
    sets: int
    reps: dict[str, Any]
    target_weight_kg: float | None
    last_weight_kg: float | None


def resolve_today_workout(
    program_exercises: list[ProgramExerciseRow], last_weights: dict[uuid.UUID, float]
) -> list[TodayExercise]:
    """Merge a program's exercises with the member's most recently logged
    weight per exercise. `last_weights` is keyed by exercise_id — the caller
    gets it with one DISTINCT ON query over workout_sets ordered by `at`
    descending, which is where the actual 'most recent' derivation happens;
    this function only merges, it never queries.
    """
    return [
        TodayExercise(
            program_exercise_id=pe.id,
            exercise_id=pe.exercise_id,
            exercise_name=pe.exercise_name,
            order_index=pe.order_index,
            sets=pe.sets,
            reps=pe.reps,
            target_weight_kg=pe.target_weight_kg,
            last_weight_kg=last_weights.get(pe.exercise_id),
        )
        for pe in program_exercises
    ]
