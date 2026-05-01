"""
FAO 1990 Soil Classification System — Tunisia edition
======================================================
Tuned for the soils that actually occur in Tunisia. Several branches of the
generic tree are pruned because the relevant soils don't exist here:
  - No peat (Histosols)        → no organic-wet question
  - No volcanic soils          → no Andosol option
  - No old/iron-rich tropical  → no Ferralsol/Plinthosol/Acrisol options
  - Tropical soils are rare    → folded into a single "reddish clay" answer

Result: 5 questions maximum, most soils classified in 1-3.

Input:  dict mapping FAO-90 soil group name -> probability of presence (0..1)
Output: (selected_soil, explanation_text)
"""

from typing import Callable

from engines.soil_FAO_constants import ALLUVIAL_SALTY, ANTHRO_CATS, ARID_CATS, CATEGORY_OF, DEVELOPED_CATS, DRY_UNIVERSE, SODIC_CATS



# ============================================================
# 2. DECISION TREE — 5 questions max
# ============================================================

def run_decision_tree(candidate_cats: set, asker: Callable) -> tuple:
    """
    Walk the decision tree and return (final_categories, trace).
    """
    trace = []
    cats = set(candidate_cats)

    def step(question, options, mapping):
        nonlocal cats
        relevant = {opt: (mapping[opt] & cats) for opt in options}
        non_empty = [opt for opt, s in relevant.items() if s]
        if len(non_empty) <= 1:
            return  # non-discriminating, skip silently
        answer = asker(question, options)
        keep = mapping[answer]
        eliminated = cats - keep
        cats &= keep
        trace.append((question, answer, eliminated))

    # --- Q1: water context (the big four-way split) ----------------
    step(
        "What's the water situation here?",
        ["Wet most of the year, marshy or boggy",
         "Gets flooded by a river or wadi",
         "A salty flat — chott, sebkha, or salt crust on top",
         "Dry land, no standing water"],
        {
            "Wet most of the year, marshy or boggy": {"wet"},
            "Gets flooded by a river or wadi": {"alluvial"},
            "A salty flat — chott, sebkha, or salt crust on top": ALLUVIAL_SALTY,
            "Dry land, no standing water": DRY_UNIVERSE,
        },
    )

    # --- Q2: sodic check (cheap, eliminates one category) ---------
    step(
        "Is the soil hard, slick, and dense when you try to dig it?",
        ["Yes, hard slick layer that water won't soak into",
         "No, it digs normally"],
        {
            "Yes, hard slick layer that water won't soak into": SODIC_CATS,
            "No, it digs normally": (DRY_UNIVERSE - SODIC_CATS),
        },
    )

    # --- Q3: arid signature (THE Tunisian question) ---------------
    step(
        "Do you see white chalky bits or sparkly crystals in the soil?",
        ["White chalky bits — lime",
         "Sparkly clear crystals — gypsum",
         "Neither, just normal-looking soil"],
        {
            "White chalky bits — lime": {"calcareous_dry"},
            "Sparkly clear crystals — gypsum": {"gypsic_dry"},
            "Neither, just normal-looking soil": (DRY_UNIVERSE - ARID_CATS - SODIC_CATS),
        },
    )

    # --- Q4: profile development (combined depth + Vertisol) ------
    step(
        "When you dig down, what do you find?",
        ["Rock right at the surface, almost no soil",
         "Loose sand all the way down, or a sand dune",
         "Young soil, no clear layers yet",
         "Heavy clay that cracks open in summer",
         "A proper soil with clear separate layers"],
        {
            "Rock right at the surface, almost no soil": {"shallow"},
            "Loose sand all the way down, or a sand dune": {"sandy"},
            "Young soil, no clear layers yet": {"young"},
            "Heavy clay that cracks open in summer": {"clay_cracking"},
            "A proper soil with clear separate layers": (DEVELOPED_CATS | ANTHRO_CATS),
        },
    )

    # --- Q5: developed-soil character (only if Q4 said "proper") --
    if cats & DEVELOPED_CATS:
        step(
            "How does the layered soil look?",
            ["Thick, dark, rich topsoil — good farmland",
             "Reddish or yellowish, with a clay layer underneath",
             "Pale washed-out layer sitting on heavy clay",
             "Brown, simple layers, nothing special",
             "Sandy with a grey ashy layer above a dark layer"],
            {
                "Thick, dark, rich topsoil — good farmland": {"dark_fertile"},
                "Reddish or yellowish, with a clay layer underneath": {"reddish_developed"},
                "Pale washed-out layer sitting on heavy clay": {"clay_bleached"},
                "Brown, simple layers, nothing special": {"moderate"},
                "Sandy with a grey ashy layer above a dark layer": {"podzol"},
            },
        )

    return cats, trace


# ============================================================
# 3. CANDIDATE FILTERING & TIE-BREAK (unchanged)
# ============================================================

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


# ============================================================
# 4. EXPLANATION BUILDER (unchanged)
# ============================================================

def build_explanation(smu_input: dict, trace: list,
                      surviving: list, ranked: list,
                      winner: tuple) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("SOIL CLASSIFICATION RESULT — TUNISIA")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Input SMU candidates (with probabilities):")
    for s, p in sorted(smu_input.items(), key=lambda x: -x[1]):
        lines.append(f"  - {s:35s}  p = {p:.2f}")
    lines.append("")

    lines.append("Decision tree steps taken:")
    if not trace:
        lines.append("  (no questions were needed — only one category present)")
    else:
        for i, (q, a, elim) in enumerate(trace, 1):
            lines.append(f"  Step {i}: {q}")
            lines.append(f"          Answer: {a}")
            if elim:
                removed_soils = [s for s in smu_input
                                 if CATEGORY_OF.get(s) in elim]
                if removed_soils:
                    lines.append(f"          Eliminated: "
                                 f"{', '.join(removed_soils)}")
    lines.append("")

    lines.append(f"Surviving candidates after tree: {len(surviving)}")
    for s, p, cat in ranked:
        lines.append(f"  - {s:35s}  p = {p:.2f}  (category: {cat})")
    lines.append("")

    if winner is None:
        lines.append("NO CANDIDATE survived. Check input or answers.")
    else:
        soil, prob, cat = winner
        if len(surviving) == 1:
            lines.append(f"FINAL CHOICE: {soil}")
            lines.append("Reason: only one candidate remained after the tree; "
                         "probability was not needed.")
        else:
            lines.append(f"FINAL CHOICE: {soil}")
            lines.append(f"Reason: {len(surviving)} candidates survived the "
                         "tree; probability tie-break selected the highest "
                         f"(p = {prob:.2f}).")
    lines.append("=" * 60)
    return "\n".join(lines)


# ============================================================
# 5. MAIN ENTRY POINT
# ============================================================

def classify_soil(smu_input: dict, asker: Callable) -> tuple:
    if not smu_input:
        return None, "Empty input — nothing to classify."

    present_cats = set()
    for soil in smu_input:
        cat = CATEGORY_OF.get(soil)
        if cat:
            present_cats.add(cat)

    if not present_cats:
        return None, "No recognised FAO-90 soils in input."

    surviving_cats, trace = run_decision_tree(present_cats, asker=asker)
    surviving = filter_candidates(smu_input, surviving_cats)
    winner, ranked = break_tie_by_probability(surviving)

    explanation = build_explanation(smu_input, trace, surviving,
                                    ranked or [], winner)
    selected = winner[0] if winner else None
    return selected, explanation


# ============================================================
# 6. DEMO
# ============================================================

if __name__ == "__main__":
    # Example: a typical northern Tunisia SMU — Medjerda valley
    example_smu = {
        "Calcic Vertisols":   0.40,
        "Calcaric Cambisols": 0.30,
        "Calcic Luvisols":    0.20,
        "Calcaric Fluvisols": 0.10,
    }

    scripted_answers = {
        "What's the water situation here?":
            "Dry land, no standing water",
        "Is the soil hard, slick, and dense when you try to dig it?":
            "No, it digs normally",
        "Do you see white chalky bits or sparkly crystals in the soil?":
            "White chalky bits — lime",
        "When you dig down, what do you find?":
            "Heavy clay that cracks open in summer",
    }

    def scripted_asker(question, options):
        ans = scripted_answers.get(question)
        if ans is None or ans not in options:
            return options[0]
        return ans

    soil, report = classify_soil(example_smu, asker=scripted_asker)
    print(report)
    print(f"\n>>> Returned soil: {soil}")