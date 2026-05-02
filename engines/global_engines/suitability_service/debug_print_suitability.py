from engines.global_engines.suitability_service.models import CropSuitabilityScore, RankingSuitability


def print_suitability_score(score: CropSuitabilityScore):
    """Prints a deep-dive of a single crop's suitability metrics."""
    status = "✅ SUITABLE" if score.is_suitable else "❌ NOT SUITABLE"
    
    print(f"\n--- Suitability Debug: {score.crop_name} ({score.crop_code}) ---")
    print(f"Status:          {status}")
    print(f"Class Label:     {score.suitability_label} (Index: {score.suitability_class})")
    print(f"Description:     {score.suitability_description}")
    
    sxx_pct = score.suitability_index_percentage
    sx2_pct = score.regional_share_percentage
    
    print(f"Suitability Idx: {score.suitability_index:<5} -> {sxx_pct:>6.2f}%")
    print(f"Regional Share:  {score.regional_share:<5} -> {sx2_pct:>6.2f}%")
    print(f"Input/Water:     {score.input_level.name} / {score.water_supply.name}")
    print("-" * 45)


def print_suitability_ranking(ranking: RankingSuitability, limit: int = 10):
    """Prints a comparison table of the top ranked crops."""
    top_crops = ranking.top_n(limit)
    
    if not top_crops:
        print("\n[!] No suitable crops found in this ranking set.")
        return

    print(f"\n{'Rank':<4} | {'Crop Name':<18} | {'SXX %':<8} | {'SX2 %':<8} | {'Class'}")
    print("-" * 60)
    
    for i, s in enumerate(top_crops, 1):
        print(f"{i:<4} | {s.crop_name[:18]:<18} | {s.suitability_index_percentage:>7.1f}% | "
              f"{s.regional_share_percentage:>7.1f}% | {s.suitability_label}")
    
    print(f"\nTotal Analyzed: {len(ranking.scores)} | Total Suitable: {len(ranking.ranks_by_suitability)}")