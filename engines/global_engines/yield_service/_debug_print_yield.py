from engines.global_engines.yield_service.models import CropYieldScore, RankingYield


def print_crop_score(score: CropYieldScore):
    """Prints a detailed breakdown of a single crop's yield data."""
    print(f"--- Yield Debug: {score.crop_name} ({score.crop_code}) ---")
    print(f"Input Level:  {score.input_level}")
    print(f"Water Supply: {score.water_supply}")
    print(f"Actual Yield: {score.actual_yield} kg/ha")
    print(f"Pot. Ceiling: {score.potential_regional_yield} kg/ha")
    
    gap = score.yield_gap
    gap_pct = score.yield_gap_pct
    
    if gap is not None:
        print(f"Yield Gap:    {gap:.2f} kg/ha ({gap_pct:.1f}%)")
    else:
        print("Yield Gap:    N/A (Missing data)")
    print(f"Has Yield:    {score.has_yield}")
    print("-" * 40)


def print_ranking_summary(ranking: RankingYield, top_n: int = 10):
    """Prints a formatted table of the ranked results."""
    ranked_list = ranking.top_n(top_n)
    
    if not ranked_list:
        print("\n[!] No yield data found in RankingYield object.")
        return

    print(f"\n{'Rank':<5} | {'Crop Name':<20} | {'Actual Yield':<15} | {'Gap %':<10}")
    print("-" * 55)
    
    for i, score in enumerate(ranked_list, 1):
        pct_str = f"{score.yield_gap_pct:.1f}%" if score.yield_gap_pct is not None else "N/A"
        print(f"{i:<5} | {score.crop_name[:20]:<20} | {score.actual_yield:<15} | {pct_str:<10}")
    
    total = len(ranking.scores)
    print(f"\n(Showing top {len(ranked_list)} out of {total} total crops analyzed)")