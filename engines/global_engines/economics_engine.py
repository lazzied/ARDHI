"""Thin PyAEZ wrapper for crop-level economic suitability calculations."""
from pyaez import EconomicSuitability


class CropEconomicSuitability:

    def __init__(self, crop_name: str, crop_cost: float, crop_yield: float, farm_price: float):
        """
        Parameters
        ----------
        crop_name  : str    - Name of the crop (e.g. "rice").
        crop_cost  : float  - Production cost [TND/ha].
        crop_yield : float  - Expected yield [t/ha].
        farm_price : float  - Historical crop price from farmer [TND/kg].
                              Converted internally to [TND/t] (* 1000).

        Attributes
        ----------
        net_revenue : float - Net revenue of the crop [TND/ha].
        """
        self.crop_name  = crop_name
        self.crop_cost  = crop_cost
        self.crop_yield = crop_yield
        self.farm_price = farm_price

        farm_price_per_tonne = farm_price * 1000

        # linregress requires at least 2 distinct x values;
        # a negligible epsilon is added to the second point.
        eps = 1e-9
        econ_su = EconomicSuitability.EconomicSuitability()
        econ_su.addACrop(
            crop_name,
            [crop_cost,  crop_cost  + eps],
            [crop_yield, crop_yield + eps],
            [farm_price_per_tonne, farm_price_per_tonne + eps],
            [[crop_yield]],
        )

        self.net_revenue = econ_su.getNetRevenue(crop_name)[0][0]

    def __str__(self):
        gross_revenue = self.farm_price * 1000 * self.crop_yield
        return (
            f"=== Economic Suitability: {self.crop_name} ===\n"
            f"  Yield        : {self.crop_yield:.2f} t/ha\n"
            f"  Farm price   : {self.farm_price:.2f} TND/kg  ({self.farm_price * 1000:.2f} TND/t)\n"
            f"  Gross revenue: {gross_revenue:.2f} TND/ha\n"
            f"  Cost         : {self.crop_cost:.2f} TND/ha\n"
            f"  Net revenue  : {self.net_revenue:.2f} TND/ha"
        )


if __name__ == "__main__":
    crop = CropEconomicSuitability(
        crop_name  = "rice",
        crop_cost  = 25.0,
        crop_yield = 2.0,
        farm_price = 343.0,
    )
    print(crop)
