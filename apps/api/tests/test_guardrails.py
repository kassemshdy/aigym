from app.domain import guardrails
from app.schemas.injuries import MemberInjury


def test_squat_blocked_for_a_recorded_knee_injury() -> None:
    injuries = [MemberInjury(body_part="knee_right", note={"ar": "ركبة", "en": "Knee"})]
    result = guardrails.check_injury_contraindication(
        injuries, muscle_group="legs", name_en="Barbell Squat"
    )
    assert result.blocked is True
    assert result.reason is not None


def test_squat_allowed_for_an_unrelated_injury() -> None:
    injuries = [MemberInjury(body_part="wrist", note={"ar": "رسغ", "en": "Wrist"})]
    result = guardrails.check_injury_contraindication(
        injuries, muscle_group="legs", name_en="Barbell Squat"
    )
    assert result.blocked is False
    assert result.reason is None


def test_squat_allowed_with_no_injuries() -> None:
    result = guardrails.check_injury_contraindication(
        [], muscle_group="legs", name_en="Barbell Squat"
    )
    assert result.blocked is False


def test_unrelated_exercise_allowed_despite_a_recorded_injury() -> None:
    injuries = [MemberInjury(body_part="knee_right", note={"ar": "ركبة", "en": "Knee"})]
    result = guardrails.check_injury_contraindication(
        injuries, muscle_group="chest", name_en="Cable Crossover"
    )
    assert result.blocked is False


def test_bench_press_blocked_for_a_shoulder_injury() -> None:
    injuries = [MemberInjury(body_part="shoulder_left", note={"ar": "كتف", "en": "Shoulder"})]
    result = guardrails.check_injury_contraindication(
        injuries, muscle_group="chest", name_en="Barbell Bench Press"
    )
    assert result.blocked is True


def test_calorie_floor_scales_with_weight() -> None:
    assert guardrails.calorie_floor(150.0) == 1500
    assert guardrails.calorie_floor(200.0) == 2000


def test_calorie_floor_never_goes_below_the_absolute_minimum() -> None:
    assert guardrails.calorie_floor(50.0) == 1200


def test_proposed_calorie_target_below_the_floor_is_blocked() -> None:
    result = guardrails.check_calorie_floor(weight_kg=80.0, proposed_kcal=700)
    assert result.blocked is True
    assert result.reason is not None


def test_proposed_calorie_target_at_or_above_the_floor_is_allowed() -> None:
    result = guardrails.check_calorie_floor(weight_kg=80.0, proposed_kcal=1800)
    assert result.blocked is False


def test_obviously_medical_text_is_flagged_in_english() -> None:
    assert guardrails.is_obviously_medical("I've had chest pain during workouts lately")


def test_obviously_medical_text_is_flagged_in_arabic() -> None:
    assert guardrails.is_obviously_medical("بعاني من ألم في الصدر وقت التمرين")


def test_ordinary_fitness_questions_are_not_flagged_as_medical() -> None:
    assert not guardrails.is_obviously_medical("How much protein should I eat after a workout?")
    assert not guardrails.is_obviously_medical("كم بروتين لازم آكل بعد التمرين؟")
