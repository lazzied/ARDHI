from engines.global_engines.yield_service.models import RankingYield


class ReportCropSuitability:

    def __init__(self, ranking: RankingYield):
        self.ranking = ranking

    def print_report(self, top_n: int = 10) -> None:
        ranked = self.ranking.top_n_by_gap_pct(top_n)

        print(f"\n{'='*55}")
        print(f"  CROP SUITABILITY REPORT — ranked by yield gap %")
        print(f"{'='*55}")
        print(f"{'#':<4} {'Crop':<30} {'Actual':>10} {'Ceiling':>10} {'Gap %':>8}")
        print(f"{'-'*55}")

        for i, score in enumerate(ranked, start=1):
            print(
                f"{i:<4} {score.crop_name:<30} "
                f"{score.actual_yield:>10.1f} "
                f"{score.potential_regional_yield:>10.1f} "
                f"{score.yield_gap_pct:>7.1f}%"
            )

        print(f"{'='*55}\n")    