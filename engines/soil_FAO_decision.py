"""
FAO 1990 Soil Classification System
====================================
Classifies a soil unit using:
  1) A decision tree (primary logic) — narrows candidates via simple questions
  2) Probability weighting (secondary logic) — breaks ties when multiple
     candidates survive the tree

Input:  dict mapping FAO-90 soil group name -> probability of presence (0..1)
        Up to 4 entries (a typical Soil Mapping Unit).
Output: (selected_soil, explanation_text)
"""

from typing import Callable


# ============================================================
# 1. CATEGORIZATION
# ------------------------------------------------------------
# Map every FAO-90 entry to a high-level category. The category
# captures the dominant defining property and drives the tree.
# ============================================================

CATEGORY_OF = {
    # A. Wet / waterlogged
    "Gleysols": "wet", "Andic Gleysols": "wet", "Dystric Gleysols": "wet",
    "Eutric Gleysols": "wet", "Gelic Gleysols": "wet", "Calcic Gleysols": "wet",
    "Mollic Gleysols": "wet", "Thionic Gleysols": "wet", "Umbric Gleysols": "wet",
    "Histosols": "organic_wet", "Fibric Histosols": "organic_wet",
    "Gelic Histosols": "organic_wet", "Folic Histosols": "organic_wet",
    "Terric Histosols": "organic_wet", "Thionic Histosols": "organic_wet",
    "Fluvisols": "alluvial", "Calcaric Fluvisols": "alluvial",
    "Dystric Fluvisols": "alluvial", "Eutric Fluvisols": "alluvial",
    "Mollic Fluvisols": "alluvial", "Salic Fluvisols": "alluvial",
    "Thionic Fluvisols": "alluvial", "Umbric Fluvisols": "alluvial",

    # B. Salty / sodic
    "Solonchaks": "saline", "Gleyic Solonchaks": "saline",
    "Haplic Solonchaks": "saline", "Gelic Solonchaks": "saline",
    "Calcic Solonchaks": "saline", "Mollic Solonchaks": "saline",
    "Sodic Solonchaks": "saline", "Gypsic Solonchaks": "saline",
    "Solonetz": "sodic", "Gleyic Solonetz": "sodic", "Haplic Solonetz": "sodic",
    "Stagnic Solonetz": "sodic", "Calcic Solonetz": "sodic",
    "Mollic Solonetz": "sodic", "Gypsic Solonetz": "sodic",

    # C. Dry / arid
    "Calcicols": "calcareous_dry", "Haplic Calcisols": "calcareous_dry",
    "Luvic Calcisols": "calcareous_dry", "Petric Calcisols": "calcareous_dry",
    "Gypsisols": "gypsic_dry", "Haplic Gypsisols": "gypsic_dry",
    "Calcic Gypsisols": "gypsic_dry", "Luvic Gypsisols": "gypsic_dry",
    "Petric Gypsisols": "gypsic_dry",

    # D. Young / undeveloped
    "Regosols": "young", "Calcaric Regosols": "young", "Dystric Regosols": "young",
    "Eutric Regosols": "young", "Gelic Regosols": "young",
    "Umbric Regosols": "young", "Gypsic Regosols": "young",
    "Arenosols": "sandy", "Albic Arenosols": "sandy", "Cambic Arenosols": "sandy",
    "Calcaric Arenosols": "sandy", "Gleyic Arenosols": "sandy",
    "Haplic Arenosols": "sandy", "Luvic Arenosols": "sandy",
    "Ferralic Arenosols": "sandy",
    "Leptosols": "shallow", "Dystric Leptosols": "shallow",
    "Eutric Leptosols": "shallow", "Gelic Leptosols": "shallow",
    "Rendzic Leptosols": "shallow", "Mollic Leptosols": "shallow",
    "Lithic Leptosols": "shallow", "Umbric Leptosols": "shallow",
    "Andosols": "volcanic", "Gleyic Andosols": "volcanic",
    "Haplic Andosols": "volcanic", "Gelic Andosols": "volcanic",
    "Mollic Andosols": "volcanic", "Umbric Andosols": "volcanic",
    "Vitric Andosols": "volcanic",

    # E. Dark fertile
    "CHERNOZEMS": "dark_fertile", "Gleyic Chernozems": "dark_fertile",
    "Haplic Chernozems": "dark_fertile", "Calcic Chernozems": "dark_fertile",
    "Luvic Chernozems": "dark_fertile", "Glossic Chernozems": "dark_fertile",
    "Kastanozems": "dark_fertile", "Haplic Kastanozems": "dark_fertile",
    "Calcic Kastanozems": "dark_fertile", "Luvic Kastanozems": "dark_fertile",
    "Gypsic Kastanozems": "dark_fertile",
    "Phaeozems": "dark_fertile", "Calcaric Phaeozems": "dark_fertile",
    "Gleyic Phaeozems": "dark_fertile", "Haplic Phaeozems": "dark_fertile",
    "Stagnic Phaeozems": "dark_fertile", "Luvic Phaeozems": "dark_fertile",
    "Greyzems": "dark_fertile", "Gleyic Greyzems": "dark_fertile",
    "Haplic Greyzems": "dark_fertile",

    # F. Clay-rich / cracking
    "Vertisols": "clay_cracking", "Dystric Vertisols": "clay_cracking",
    "Eutric Vertisols": "clay_cracking", "Calcic Vertisols": "clay_cracking",
    "Gypsic Vertisols": "clay_cracking",
    "Planosols": "clay_bleached", "Dystric Planosols": "clay_bleached",
    "Eutric Planosols": "clay_bleached", "Gelic Planosols": "clay_bleached",
    "Mollic Planosols": "clay_bleached", "Umbric Planosols": "clay_bleached",
    "Nitisols": "clay_tropical", "Haplic Nitisols": "clay_tropical",
    "Rhodic Nitisols": "clay_tropical", "Humic Nitisols": "clay_tropical",

    # G. Weathered tropical
    "Ferralsols": "tropical_old", "Geric Ferralsols": "tropical_old",
    "Haplic Ferralsols": "tropical_old", "Plinthic Ferralsols": "tropical_old",
    "Rhodic Ferralsols": "tropical_old", "Humic Ferralsols": "tropical_old",
    "Xanthic Ferralsols": "tropical_old",
    "Acrisols": "tropical_leached", "Ferric Acrisols": "tropical_leached",
    "Gleyic Acrisols": "tropical_leached", "Haplic Acrisols": "tropical_leached",
    "Plinthic Acrisols": "tropical_leached", "Humic Acrisols": "tropical_leached",
    "Lixisols": "tropical_fertile", "Albic Lixisols": "tropical_fertile",
    "Ferric Lixisols": "tropical_fertile", "Gleyic Lixisols": "tropical_fertile",
    "Haplic Lixisols": "tropical_fertile", "Stagnic Lixisols": "tropical_fertile",
    "Plinthic Lixisols": "tropical_fertile",
    "Alisols": "tropical_acidic", "Ferric Alisols": "tropical_acidic",
    "Gleyic Alisols": "tropical_acidic", "Haplic Alisols": "tropical_acidic",
    "Stagnic Alisols": "tropical_acidic", "Plinthic Alisols": "tropical_acidic",
    "Humic Alisols": "tropical_acidic",
    "Plinthosols": "iron_hardpan", "Albic Plinthosols": "iron_hardpan",
    "Dystric Plinthosols": "iron_hardpan", "Eutric Plinthosols": "iron_hardpan",
    "Humic Plinthosols": "iron_hardpan",

    # H. Moderately developed (temperate)
    "Cambisols": "moderate", "Calcaric Cambisols": "moderate",
    "Dystric Cambisols": "moderate", "Eutric Cambisols": "moderate",
    "Gleyic Cambisols": "moderate", "Gelic Cambisols": "moderate",
    "Ferralic Cambisols": "moderate", "Humic Cambisols": "moderate",
    "Vertic Cambisols": "moderate", "Chromic Cambisols": "moderate",
    "Luvsiols": "luvic", "Albic Luvsiols": "luvic", "Ferric Luvisols": "luvic",
    "Gleyic Luvisols": "luvic", "Haplic Luvisols": "luvic",
    "Stagnic Luvisols": "luvic", "Calcic Luvisols": "luvic",
    "Vertic Luvisols": "luvic", "Chromic Luvisols": "luvic",
    "Podzols": "podzol", "Cambic Podzols": "podzol", "Carbic Podzols": "podzol",
    "Ferric Podzols": "podzol", "Gleyic Podzols": "podzol",
    "Haplic Podzols": "podzol", "Gelic Podzols": "podzol",
    "Podzoluvisols": "podzoluvic", "Dystric Podzoluvisols": "podzoluvic",
    "Eutric Podzoluvisols": "podzoluvic", "Gleyic Podzoluvisols": "podzoluvic",
    "Gelic Podzoluvisols": "podzoluvic", "Stagnic Podzoluvisols": "podzoluvic",

    # I. Human-modified
    "Anthrosols": "anthropic", "Aric Anthrosols": "anthropic",
    "Cumulic Anthrosols": "anthropic", "Fimic Anthrosols": "anthropic",
    "Urbic Anthrosols": "anthropic",

    # J. Non-soil / special
    "Dunes & shift.sands": "non_soil", "Fishpond": "non_soil",
    "Glaciers": "non_soil", "Humanly disturbed": "non_soil",
    "Island": "non_soil", "Marsh": "non_soil", "No Data": "non_soil",
    "Rock outcrops": "non_soil", "Salt flats": "non_soil",
    "Urban, mining, etc.": "non_soil", "Water bodies": "non_soil",
    "Inland water, salt": "non_soil",
}


# ============================================================
# 2. DECISION TREE
# ------------------------------------------------------------
# Each node = one yes/no question with a category-set effect.
# Walking the tree narrows the candidate categories.
# ============================================================

# Group categories into broad branches so the first questions
# eliminate large chunks at once.
WET_CATS       = {"wet", "organic_wet", "alluvial"}
SALTY_CATS     = {"saline", "sodic"}
DRY_CATS       = {"calcareous_dry", "gypsic_dry"}
YOUNG_CATS     = {"young", "sandy", "shallow", "volcanic"}
DARK_CATS      = {"dark_fertile"}
CLAY_CATS      = {"clay_cracking", "clay_bleached", "clay_tropical"}
TROPICAL_CATS  = {"tropical_old", "tropical_leached", "tropical_fertile",
                  "tropical_acidic", "iron_hardpan"}
TEMPERATE_CATS = {"moderate", "luvic", "podzol", "podzoluvic"}
ANTHRO_CATS    = {"anthropic"}
NONSOIL_CATS   = {"non_soil"}


def ask(prompt: str) -> bool:
    """Simple yes/no prompt. Returns True for yes."""
    while True:
        ans = input(f"  {prompt} [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("    Please answer y or n.")


def ask_choice(prompt: str, options: list) -> str:
    """Multiple-choice prompt. Returns the chosen option string."""
    print(f"  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        ans = input("  Choose number: ").strip()
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1]
        print("    Invalid choice.")


def run_decision_tree(candidate_cats: set, asker: Callable = None) -> tuple:
    """
    Walk the decision tree and return (final_categories, trace).
    `asker` is a callable(question, options) -> answer; defaults to interactive.
    `final_categories` is the set of categories still in play after the tree.
    `trace` is a list of (question, answer, eliminated_cats) tuples.
    """
    if asker is None:
        def asker(q, opts):
            return ask_choice(q, opts)

    trace = []
    cats = set(candidate_cats)

    def step(question, options, mapping):
        """Ask one question; mapping = {answer: keep_cats_set}."""
        nonlocal cats
        # Skip if all surviving candidates would answer the same way
        relevant = {opt: (mapping[opt] & cats) for opt in options}
        non_empty = [opt for opt, s in relevant.items() if s]
        if len(non_empty) <= 1:
            return  # non-discriminating, skip silently
        answer = asker(question, options)
        keep = mapping[answer]
        eliminated = cats - keep
        cats &= keep
        trace.append((question, answer, eliminated))

    # --- Q1: wetness -------------------------------------------------
    step(
        "Is the soil usually wet, waterlogged, or near a river?",
        ["Almost always wet / peaty", "Often flooded by rivers",
         "Wet only seasonally", "No, mostly dry"],
        {
            "Almost always wet / peaty": WET_CATS,
            "Often flooded by rivers": {"alluvial"},
            "Wet only seasonally": WET_CATS | CLAY_CATS | TEMPERATE_CATS
                                   | TROPICAL_CATS | DARK_CATS | YOUNG_CATS
                                   | ANTHRO_CATS | NONSOIL_CATS,
            "No, mostly dry": (set(CATEGORY_OF.values()) - WET_CATS),
        },
    )

    # --- Q2: organic vs mineral within wet ---------------------------
    if cats & WET_CATS:
        step(
            "Is the topsoil dark, spongy and made mostly of decayed plants?",
            ["Yes, peat-like", "No, normal mineral soil"],
            {
                "Yes, peat-like": {"organic_wet"},
                "No, normal mineral soil": (cats - {"organic_wet"}),
            },
        )

    # --- Q3: salinity ------------------------------------------------
    step(
        "Is there a salt crust or does the soil feel salty/sticky-hard?",
        ["Salty white crust", "Hard slick dense layer", "Neither"],
        {
            "Salty white crust": {"saline"},
            "Hard slick dense layer": {"sodic"},
            "Neither": (set(CATEGORY_OF.values()) - SALTY_CATS),
        },
    )

    # --- Q4: aridity / lime / gypsum --------------------------------
    step(
        "Is the climate dry and is there visible lime or gypsum?",
        ["Dry with lots of lime/chalk", "Dry with gypsum crystals",
         "Dry but neither", "Not dry"],
        {
            "Dry with lots of lime/chalk": {"calcareous_dry"},
            "Dry with gypsum crystals": {"gypsic_dry"},
            "Dry but neither": YOUNG_CATS,
            "Not dry": (set(CATEGORY_OF.values()) - DRY_CATS),
        },
    )

    # --- Q5: human modification --------------------------------------
    step(
        "Has the soil been heavily modified by human activity (terracing, "
        "long cultivation, urban fill)?",
        ["Yes, clearly human-made profile", "No, natural"],
        {
            "Yes, clearly human-made profile": ANTHRO_CATS,
            "No, natural": (set(CATEGORY_OF.values()) - ANTHRO_CATS),
        },
    )

    # --- Q6: development / depth -------------------------------------
    step(
        "How developed is the soil profile?",
        ["Very shallow, rock close to surface", "Deep loose sand",
         "Young with no clear layers", "Dark soil from volcanic ash",
         "Well-developed with clear layers"],
        {
            "Very shallow, rock close to surface": {"shallow"},
            "Deep loose sand": {"sandy"},
            "Young with no clear layers": {"young"},
            "Dark soil from volcanic ash": {"volcanic"},
            "Well-developed with clear layers": (DARK_CATS | CLAY_CATS
                                                 | TROPICAL_CATS
                                                 | TEMPERATE_CATS),
        },
    )

    # --- Q7: developed-soil appearance ------------------------------
    if cats & (DARK_CATS | CLAY_CATS | TROPICAL_CATS | TEMPERATE_CATS):
        step(
            "What best describes the developed soil?",
            ["Thick dark fertile topsoil",
             "Heavy clay that cracks when dry",
             "Reddish/yellowish, old tropical look",
             "Brown, temperate, normal layers"],
            {
                "Thick dark fertile topsoil": DARK_CATS,
                "Heavy clay that cracks when dry": CLAY_CATS,
                "Reddish/yellowish, old tropical look": TROPICAL_CATS,
                "Brown, temperate, normal layers": TEMPERATE_CATS,
            },
        )

    # --- Q8a: tropical refinement -----------------------------------
    if cats & TROPICAL_CATS:
        step(
            "Among the tropical features, which fits best?",
            ["Very deep red, uniform, very old",
             "Clay layer + low fertility / acidic",
             "Clay layer + reasonable fertility",
             "Very acidic with aluminium issues",
             "Hard iron-rich layer (plinthite)"],
            {
                "Very deep red, uniform, very old": {"tropical_old"},
                "Clay layer + low fertility / acidic": {"tropical_leached"},
                "Clay layer + reasonable fertility": {"tropical_fertile"},
                "Very acidic with aluminium issues": {"tropical_acidic"},
                "Hard iron-rich layer (plinthite)": {"iron_hardpan"},
            },
        )

    # --- Q8b: clay refinement ---------------------------------------
    if cats & CLAY_CATS:
        step(
            "Among the clay-rich features, which fits best?",
            ["Deep cracks when dry, sticky when wet",
             "Bleached layer over heavy clay",
             "Shiny clay surfaces, tropical"],
            {
                "Deep cracks when dry, sticky when wet": {"clay_cracking"},
                "Bleached layer over heavy clay": {"clay_bleached"},
                "Shiny clay surfaces, tropical": {"clay_tropical"},
            },
        )

    # --- Q8c: temperate refinement ----------------------------------
    if cats & TEMPERATE_CATS:
        step(
            "Among the temperate features, which fits best?",
            ["Brown, simple profile",
             "Clay accumulation with high fertility",
             "Sandy with ash-grey layer + dark layer below",
             "Bleached layer with clay below"],
            {
                "Brown, simple profile": {"moderate"},
                "Clay accumulation with high fertility": {"luvic"},
                "Sandy with ash-grey layer + dark layer below": {"podzol"},
                "Bleached layer with clay below": {"podzoluvic"},
            },
        )

    return cats, trace


# ============================================================
# 3. CANDIDATE FILTERING
# ------------------------------------------------------------
# Convert the input dict (FAO-90 names + probabilities) into
# a working candidate list, filter via the tree, then break ties
# using probability.
# ============================================================

def filter_candidates(smu_input: dict, surviving_cats: set) -> list:
    """Keep only candidates whose category survived the decision tree."""
    out = []
    for soil, prob in smu_input.items():
        cat = CATEGORY_OF.get(soil)
        if cat is None:
            # Unknown name -> keep with neutral category so we don't lose it
            out.append((soil, prob, "unknown"))
        elif cat in surviving_cats:
            out.append((soil, prob, cat))
    return out


def break_tie_by_probability(candidates: list) -> tuple:
    """Pick the highest-probability candidate; deterministic on ties (alpha)."""
    if not candidates:
        return None, None
    # Sort by (-probability, name) for deterministic output
    candidates_sorted = sorted(candidates, key=lambda x: (-x[1], x[0]))
    winner = candidates_sorted[0]
    return winner, candidates_sorted


# ============================================================
# 4. EXPLANATION BUILDER
# ============================================================

def build_explanation(smu_input: dict, trace: list,
                      surviving: list, ranked: list,
                      winner: tuple) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("SOIL CLASSIFICATION RESULT")
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
                # Show which input soils this step removed
                removed_soils = [s for s in smu_input
                                 if CATEGORY_OF.get(s) in elim]
                if removed_soils:
                    lines.append(f"          Eliminated: "
                                 f"{', '.join(removed_soils)}")
    lines.append("")

    lines.append(f"Surviving candidates after tree: "
                 f"{len(surviving)}")
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

def classify_soil(smu_input: dict, asker: Callable = None) -> tuple:
    """
    Main API.
    Args:
      smu_input: dict {soil_name: probability}
      asker: optional callable (question, options) -> answer for testing.
             If None, uses interactive console input.
    Returns:
      (selected_soil_name, explanation_string)
    """
    if not smu_input:
        return None, "Empty input — nothing to classify."

    # Categories actually present in this SMU
    present_cats = set()
    for soil in smu_input:
        cat = CATEGORY_OF.get(soil)
        if cat:
            present_cats.add(cat)

    if not present_cats:
        return None, "No recognised FAO-90 soils in input."

    # Walk the decision tree, restricted to present categories
    surviving_cats, trace = run_decision_tree(present_cats, asker=asker)

    # Filter input by surviving categories
    surviving = filter_candidates(smu_input, surviving_cats)

    # Probability tie-break
    winner, ranked = break_tie_by_probability(surviving)

    explanation = build_explanation(smu_input, trace, surviving,
                                    ranked or [], winner)
    selected = winner[0] if winner else None
    return selected, explanation


# ============================================================
# 6. INTERACTIVE USER SYSTEM
# ------------------------------------------------------------
# Handles all user-facing I/O:
#   - collect SMU input (soil names + probabilities)
#   - present each tree question with numbered options
#   - validate input, allow re-entry, show progress
# ============================================================

# All accepted FAO-90 names, taken from CATEGORY_OF keys
KNOWN_SOILS = sorted(CATEGORY_OF.keys())


def _print_header(text: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n{text}\n{bar}")


def _print_section(text: str) -> None:
    print(f"\n--- {text} ---")


def interactive_asker(question: str, options: list) -> str:
    """
    Display a question with numbered options and return the chosen option.
    This is the function the decision tree calls for every step.
    """
    print(f"\n? {question}")
    for i, opt in enumerate(options, 1):
        print(f"   {i}. {opt}")
    while True:
        raw = input("   Your choice (number): ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                chosen = options[idx - 1]
                print(f"   -> {chosen}")
                return chosen
        print("   ! Please enter a valid number from the list.")


def _suggest_match(name: str, choices: list, limit: int = 3) -> list:
    """Return up to `limit` close matches for a mistyped soil name."""
    name_low = name.lower()
    # Cheap substring match first; good enough without external libs
    starts = [c for c in choices if c.lower().startswith(name_low)]
    contains = [c for c in choices if name_low in c.lower() and c not in starts]
    return (starts + contains)[:limit]


def collect_smu_input() -> dict:
    """
    Ask the user for the SMU's soil candidates and their probabilities.
    Returns a dict {soil_name: probability}.
    """
    _print_section("Step 1: Enter the soils present in this SMU")
    print("Enter 1 to 4 soil candidates from the FAO-90 list.")
    print("For each candidate, give the soil name and its probability (0..1).")
    print("Type 'list' to see all valid names, or 'done' when finished.\n")

    smu = {}
    while len(smu) < 4:
        slot = len(smu) + 1
        name = input(f"  Soil #{slot} name (or 'done' / 'list'): ").strip()

        if name.lower() == "done":
            if not smu:
                print("  ! At least one soil is required.")
                continue
            break
        if name.lower() == "list":
            print("\n  Valid FAO-90 names (truncated to first 40):")
            for n in KNOWN_SOILS[:40]:
                print(f"    - {n}")
            print(f"  ... ({len(KNOWN_SOILS)} total)\n")
            continue
        if not name:
            continue

        if name not in CATEGORY_OF:
            suggestions = _suggest_match(name, KNOWN_SOILS)
            if suggestions:
                print(f"  ! '{name}' not recognised. Did you mean: "
                      f"{', '.join(suggestions)} ?")
            else:
                print(f"  ! '{name}' is not in the FAO-90 list. "
                      "Type 'list' to browse names.")
            continue
        if name in smu:
            print("  ! Already added that soil.")
            continue

        # Probability
        while True:
            raw = input(f"  Probability for '{name}' (0..1): ").strip()
            try:
                p = float(raw)
                if 0.0 <= p <= 1.0:
                    break
                print("    ! Must be between 0 and 1.")
            except ValueError:
                print("    ! Not a valid number.")
        smu[name] = p

        if len(smu) < 4:
            more = input("  Add another soil? [y/n]: ").strip().lower()
            if more not in ("y", "yes"):
                break

    return smu


def run_interactive_session() -> tuple:
    """
    Full interactive loop:
      1) collect SMU input
      2) walk the decision tree with the user
      3) print the explanation report
    Returns (selected_soil, explanation).
    """
    _print_header("FAO 1990 SOIL CLASSIFICATION — INTERACTIVE")
    print("This tool helps you identify the most likely soil group within")
    print("a Soil Mapping Unit (SMU) by answering a few simple questions.")

    # 1. Input
    smu = collect_smu_input()
    if not smu:
        print("\nNo input provided. Exiting.")
        return None, ""

    print("\nYou entered:")
    for s, p in sorted(smu.items(), key=lambda x: -x[1]):
        print(f"   - {s:35s}  p = {p:.2f}")

    # 2. Tree walk
    _print_section("Step 2: Answer the questions below")
    print("Answer based on what you observe in the field. Questions that")
    print("can't distinguish your remaining candidates will be skipped.\n")

    selected, explanation = classify_soil(smu, asker=interactive_asker)

    # 3. Report
    _print_section("Step 3: Result")
    print(explanation)
    return selected, explanation


# ============================================================
# 7. DEMO (runs only when executed directly)
# ============================================================

if __name__ == "__main__":
    import sys
    """
    python soil_classifier.py          # interactive mode (default)
    python soil_classifier.py --demo   # scripted demo (no input needed)
    
    """
    # Run interactively unless --demo flag is passed
    if "--demo" not in sys.argv:
        try:
            run_interactive_session()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSession ended by user.")
        sys.exit(0)

    # ---- Scripted demo (python soil_classifier.py --demo) ----
    example_smu = {
        "Haplic Acrisols":  0.45,
        "Plinthic Acrisols": 0.25,
        "Ferric Lixisols":  0.20,
        "Eutric Cambisols": 0.10,
    }

    scripted_answers = {
        "Is the soil usually wet, waterlogged, or near a river?": "No, mostly dry",
        "Is there a salt crust or does the soil feel salty/sticky-hard?": "Neither",
        "Is the climate dry and is there visible lime or gypsum?": "Not dry",
        "Has the soil been heavily modified by human activity (terracing, "
        "long cultivation, urban fill)?": "No, natural",
        "How developed is the soil profile?":
            "Well-developed with clear layers",
        "What best describes the developed soil?":
            "Reddish/yellowish, old tropical look",
        "Among the tropical features, which fits best?":
            "Clay layer + low fertility / acidic",
    }

    def scripted_asker(question, options):
        ans = scripted_answers.get(question)
        if ans is None or ans not in options:
            # Fall back to first option to keep demo self-contained
            return options[0]
        return ans

    soil, report = classify_soil(example_smu, asker=scripted_asker)
    print(report)
    print(f"\n>>> Returned soil: {soil}")