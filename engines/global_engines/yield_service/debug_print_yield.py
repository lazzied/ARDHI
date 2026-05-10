"""Developer-only pretty printers for yield scores and ranking snapshots."""
from engines.global_engines.yield_service.models import CropYieldScore, RankingYield


def print_crop_score(score: CropYieldScore):
    """Prints a detailed breakdown of a single crop's yield data."""
    print(f"--- Yield Debug: {score.crop_name} ({score.crop_code}) ---")
    print(f"Input Level:  {score.input_level}")
    print(f"Water Supply: {score.water_supply}")
    print(f"Actual Yield: {score.actual_yield} kg/ha")
    print(f"Pot. Ceiling: {score.regional_yield} kg/ha")   # FIXED: was score.potential_regional_yield

    gap = score.yield_gap
    gap_pct = score.yield_gap_pct

    if gap is not None:
        print(f"Yield Gap:    {gap:.2f} kg/ha ({gap_pct:.1f}%)")
    else:
        print("Yield Gap:    N/A (Missing data)")
    print(f"Has Yield:    {score.has_yield}")
    print("-" * 40)


# ---------------------------------------------------------------------------
# Shared header / row helpers
# ---------------------------------------------------------------------------

_HEADER = (
    f"\n{'Rank':<5} | {'Crop Name':<20} | {'Actual Yield':<15} | "
    f"{'Regional Yield':<16} | {'Gap kg/ha':<12} | {'Gap %':<10}"
)
_DIVIDER = "-" * 84


def _row(i: int, score: CropYieldScore) -> str:
    regional_str = f"{score.regional_yield} kg/ha" if score.regional_yield is not None else "N/A"
    gap_str      = f"{score.yield_gap:.2f} kg/ha"  if score.yield_gap      is not None else "N/A"
    pct_str      = f"{score.yield_gap_pct:.1f}%"   if score.yield_gap_pct  is not None else "N/A"
    return (
        f"{i:<5} | {score.crop_name[:20]:<20} | {score.actual_yield:<15} | "
        f"{regional_str:<16} | {gap_str:<12} | {pct_str:<10}"
    )


# ---------------------------------------------------------------------------
# Rank by actual yield (original behaviour)
# ---------------------------------------------------------------------------

def print_ranking_summary(ranking: RankingYield, top_n: int = 10):
    """Prints a formatted table ranked by actual yield descending."""
    ranked_list = ranking.top_n(top_n)

    if not ranked_list:
        print("\n[!] No yield data found in RankingYield object.")
        return

    print(_HEADER)
    print(_DIVIDER)
    for i, score in enumerate(ranked_list, 1):
        print(_row(i, score))

    total = len(ranking.scores)
    print(f"\n(Showing top {len(ranked_list)} out of {total} total crops analyzed)")


def format_ranking_summary(ranking: RankingYield, top_n: int = 10) -> str:
    """Returns a formatted string ranked by actual yield descending."""
    ranked_list = ranking.top_n(top_n)
    lines = []

    if not ranked_list:
        lines.append("\n[!] No yield data found in RankingYield object.")
        return "\n".join(lines)

    lines.append(_HEADER)
    lines.append(_DIVIDER)
    for i, score in enumerate(ranked_list, 1):
        lines.append(_row(i, score))

    total = len(ranking.scores)
    lines.append(f"\n(Showing top {len(ranked_list)} out of {total} total crops analyzed)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rank by yield gap ascending  (lowest gap = rank 1, negatives included)
# ---------------------------------------------------------------------------

def print_gap_ranking_summary(ranking: RankingYield, top_n: int = 10):
    """
    Prints a formatted table ranked by yield gap ascending.

    Rank 1 = smallest (or most-negative) gap, meaning the crop already meets
    or exceeds its regional ceiling. Negative gaps are included and rank first.
    """
    ranked_list = ranking.ranked_by_gap[:top_n]

    if not ranked_list:
        print("\n[!] No gap data found in RankingYield object.")
        return

    print("\n[Gap Ranking — lowest gap first; negative = exceeds regional ceiling]")
    print(_HEADER)
    print(_DIVIDER)
    for i, score in enumerate(ranked_list, 1):
        print(_row(i, score))

    total = len(ranking.ranked_by_gap)
    print(f"\n(Showing top {len(ranked_list)} out of {total} crops with gap data)")


def format_gap_ranking_summary(ranking: RankingYield, top_n: int = 10) -> str:
    """
    Returns a formatted string ranked by yield gap ascending.

    Rank 1 = smallest (or most-negative) gap, meaning the crop already meets
    or exceeds its regional ceiling. Negative gaps are included and rank first.
    """
    ranked_list = ranking.ranked_by_gap[:top_n]
    lines = []

    if not ranked_list:
        lines.append("\n[!] No gap data found in RankingYield object.")
        return "\n".join(lines)

    lines.append("\n[Gap Ranking — lowest gap first; negative = exceeds regional ceiling]")
    lines.append(_HEADER)
    lines.append(_DIVIDER)
    for i, score in enumerate(ranked_list, 1):
        lines.append(_row(i, score))

    total = len(ranking.ranked_by_gap)
    lines.append(f"\n(Showing top {len(ranked_list)} out of {total} crops with gap data)")
    return "\n".join(lines)