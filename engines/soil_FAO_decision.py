"""
FAO 1990 Soil Classification System - Tunisia edition
=====================================================
Tuned for the soils that actually occur in Tunisia.

This module now supports both:
1. Dynamic step-by-step progression from partial answers.
2. The original classify_soil(smu_input, asker) workflow.
"""

from dataclasses import dataclass
from typing import Callable

from engines.soil_FAO_constants import (
    ALLUVIAL_SALTY,
    ANTHRO_CATS,
    ARID_CATS,
    CATEGORY_OF,
    DEVELOPED_CATS,
    DRY_UNIVERSE,
    SODIC_CATS,
)


@dataclass(frozen=True)
class DecisionQuestion:
    id: str
    question: str
    options: tuple[str, ...]
    mapping: dict[str, set[str]]
    required_categories: set[str] | None = None


QUESTION_FLOW = (
    DecisionQuestion(
        id="water_context",
        question="What's the water situation here?",
        options=(
            "Wet most of the year, marshy or boggy",
            "Gets flooded by a river or wadi",
            "A salty flat - chott, sebkha, or salt crust on top",
            "Dry land, no standing water",
        ),
        mapping={
            "Wet most of the year, marshy or boggy": {"wet"},
            "Gets flooded by a river or wadi": {"alluvial"},
            "A salty flat - chott, sebkha, or salt crust on top": ALLUVIAL_SALTY,
            "Dry land, no standing water": DRY_UNIVERSE,
        },
    ),
    DecisionQuestion(
        id="sodic_check",
        question="Is the soil hard, slick, and dense when you try to dig it?",
        options=(
            "Yes, hard slick layer that water won't soak into",
            "No, it digs normally",
        ),
        mapping={
            "Yes, hard slick layer that water won't soak into": SODIC_CATS,
            "No, it digs normally": (DRY_UNIVERSE - SODIC_CATS),
        },
    ),
    DecisionQuestion(
        id="arid_signature",
        question="Do you see white chalky bits or sparkly crystals in the soil?",
        options=(
            "White chalky bits - lime",
            "Sparkly clear crystals - gypsum",
            "Neither, just normal-looking soil",
        ),
        mapping={
            "White chalky bits - lime": {"calcareous_dry"},
            "Sparkly clear crystals - gypsum": {"gypsic_dry"},
            "Neither, just normal-looking soil": (DRY_UNIVERSE - ARID_CATS - SODIC_CATS),
        },
    ),
    DecisionQuestion(
        id="profile_development",
        question="When you dig down, what do you find?",
        options=(
            "Rock right at the surface, almost no soil",
            "Loose sand all the way down, or a sand dune",
            "Young soil, no clear layers yet",
            "Heavy clay that cracks open in summer",
            "A proper soil with clear separate layers",
        ),
        mapping={
            "Rock right at the surface, almost no soil": {"shallow"},
            "Loose sand all the way down, or a sand dune": {"sandy"},
            "Young soil, no clear layers yet": {"young"},
            "Heavy clay that cracks open in summer": {"clay_cracking"},
            "A proper soil with clear separate layers": (DEVELOPED_CATS | ANTHRO_CATS),
        },
    ),
    DecisionQuestion(
        id="developed_soil_character",
        question="How does the layered soil look?",
        options=(
            "Thick, dark, rich topsoil - good farmland",
            "Reddish or yellowish, with a clay layer underneath",
            "Pale washed-out layer sitting on heavy clay",
            "Brown, simple layers, nothing special",
            "Sandy with a grey ashy layer above a dark layer",
        ),
        mapping={
            "Thick, dark, rich topsoil - good farmland": {"dark_fertile"},
            "Reddish or yellowish, with a clay layer underneath": {"reddish_developed"},
            "Pale washed-out layer sitting on heavy clay": {"clay_bleached"},
            "Brown, simple layers, nothing special": {"moderate"},
            "Sandy with a grey ashy layer above a dark layer": {"podzol"},
        },
        required_categories=DEVELOPED_CATS,
    ),
)


def get_present_categories(smu_input: dict) -> set[str]:
    return {CATEGORY_OF[soil] for soil in smu_input if CATEGORY_OF.get(soil)}


def _get_relevant_options(question: DecisionQuestion, cats: set[str]) -> list[str]:
    return [option for option in question.options if question.mapping[option] & cats]


def evaluate_answers(
    candidate_cats: set[str],
    answers: dict[str, str] | None = None,
) -> tuple[set[str], list[tuple], DecisionQuestion | None]:
    trace = []
    cats = set(candidate_cats)
    answers = answers or {}

    for question in QUESTION_FLOW:
        if question.required_categories and not (cats & question.required_categories):
            continue

        relevant_options = _get_relevant_options(question, cats)
        if len(relevant_options) <= 1:
            continue

        answer = answers.get(question.id)
        if answer is None:
            return cats, trace, question
        if answer not in question.mapping:
            raise ValueError(f"Invalid answer for '{question.id}': {answer}")
        if answer not in relevant_options:
            raise ValueError(
                f"Irrelevant answer for '{question.id}' given current candidates: {answer}"
            )

        keep = question.mapping[answer]
        eliminated = cats - keep
        cats &= keep
        trace.append((question.question, answer, eliminated))

    return cats, trace, None


def get_next_question(smu_input: dict, answers: dict[str, str] | None = None) -> dict | None:
    if not smu_input:
        return None

    present_cats = get_present_categories(smu_input)
    if not present_cats:
        return None

    surviving_cats, _, pending_question = evaluate_answers(present_cats, answers)
    if pending_question is None:
        return None

    return {
        "id": pending_question.id,
        "question": pending_question.question,
        "options": _get_relevant_options(pending_question, surviving_cats),
    }


def run_decision_tree(candidate_cats: set, asker: Callable) -> tuple:
    """
    Walk the decision tree and return (final_categories, trace).
    """
    answers: dict[str, str] = {}

    while True:
        cats, trace, pending_question = evaluate_answers(candidate_cats, answers)
        if pending_question is None:
            return cats, trace

        answers[pending_question.id] = asker(
            pending_question.question,
            list(_get_relevant_options(pending_question, cats)),
        )


def filter_candidates(smu_input: dict, surviving_cats: set) -> list:
    out = []
    for soil, prob in smu_input.items():
        cat = CATEGORY_OF.get(soil)
        if cat is None:
            out.append((soil, prob, "unknown"))
        elif cat in surviving_cats:
            out.append((soil, prob, cat))
    return out


def break_tie_by_probability(candidates: list) -> tuple:
    if not candidates:
        return None, None
    candidates_sorted = sorted(candidates, key=lambda x: (-x[1], x[0]))
    return candidates_sorted[0], candidates_sorted


def build_explanation(
    smu_input: dict,
    trace: list,
    surviving: list,
    ranked: list,
    winner: tuple,
) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("SOIL CLASSIFICATION RESULT - TUNISIA")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Input SMU candidates (with probabilities):")
    for s, p in sorted(smu_input.items(), key=lambda x: -x[1]):
        lines.append(f"  - {s:35s}  p = {p:.2f}")
    lines.append("")

    lines.append("Decision tree steps taken:")
    if not trace:
        lines.append("  (no questions were needed - only one category present)")
    else:
        for i, (q, a, elim) in enumerate(trace, 1):
            lines.append(f"  Step {i}: {q}")
            lines.append(f"          Answer: {a}")
            if elim:
                removed_soils = [s for s in smu_input if CATEGORY_OF.get(s) in elim]
                if removed_soils:
                    lines.append(f"          Eliminated: {', '.join(removed_soils)}")
    lines.append("")

    lines.append(f"Surviving candidates after tree: {len(surviving)}")
    for s, p, cat in ranked:
        lines.append(f"  - {s:35s}  p = {p:.2f}  (category: {cat})")
    lines.append("")

    if winner is None:
        lines.append("NO CANDIDATE survived. Check input or answers.")
    else:
        soil, prob, _ = winner
        lines.append(f"FINAL CHOICE: {soil}")
        if len(surviving) == 1:
            lines.append(
                "Reason: only one candidate remained after the tree; probability was not needed."
            )
        else:
            lines.append(
                f"Reason: {len(surviving)} candidates survived the tree; probability tie-break "
                f"selected the highest (p = {prob:.2f})."
            )
    lines.append("=" * 60)
    return "\n".join(lines)


def classify_soil(smu_input: dict, asker: Callable) -> tuple:
    if not smu_input:
        return None, "Empty input - nothing to classify."

    present_cats = get_present_categories(smu_input)
    if not present_cats:
        return None, "No recognised FAO-90 soils in input."

    surviving_cats, trace = run_decision_tree(present_cats, asker=asker)
    surviving = filter_candidates(smu_input, surviving_cats)
    winner, ranked = break_tie_by_probability(surviving)

    explanation = build_explanation(smu_input, trace, surviving, ranked or [], winner)
    selected = winner[0] if winner else None
    return selected, explanation


def classify_soil_dynamic(smu_input: dict, answers: dict[str, str] | None = None) -> dict:
    if not smu_input:
        return {
            "status": "error",
            "message": "Empty input - nothing to classify.",
        }

    present_cats = get_present_categories(smu_input)
    if not present_cats:
        return {
            "status": "error",
            "message": "No recognised FAO-90 soils in input.",
        }

    surviving_cats, trace, pending_question = evaluate_answers(present_cats, answers)
    surviving = filter_candidates(smu_input, surviving_cats)
    winner, ranked = break_tie_by_probability(surviving)

    if pending_question is not None:
        return {
            "status": "question",
            "trace": trace,
            "surviving_categories": sorted(surviving_cats),
            "question": {
                "id": pending_question.id,
                "question": pending_question.question,
                "options": _get_relevant_options(pending_question, surviving_cats),
            },
        }

    explanation = build_explanation(smu_input, trace, surviving, ranked or [], winner)
    return {
        "status": "complete",
        "selected_soil": winner[0] if winner else None,
        "surviving_categories": sorted(surviving_cats),
        "surviving_candidates": ranked or [],
        "trace": trace,
        "explanation": explanation,
    }


if __name__ == "__main__":
    example_smu = {
        "Calcic Vertisols": 0.40,
        "Calcaric Cambisols": 0.30,
        "Calcic Luvisols": 0.20,
        "Calcaric Fluvisols": 0.10,
    }

    scripted_answers = {
        "water_context": "Dry land, no standing water",
        "sodic_check": "No, it digs normally",
        "arid_signature": "White chalky bits - lime",
        "profile_development": "Heavy clay that cracks open in summer",
    }

    result = classify_soil_dynamic(example_smu, scripted_answers)
    print(result["explanation"])
    print(f"\n>>> Returned soil: {result['selected_soil']}")
