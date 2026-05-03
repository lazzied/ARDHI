
"""Lightweight formatter around EcoCrop crop reference information."""

from ardhi.db.ecocrop import EcoCropRepository


class CropInfo:

    SECTIONS = {
        "General Info": ["id", "common_name", "scientific_name", "life_form", "physiology", "habit", "category", "life_span"],
        "Attributes & Notes": ["plant_attributes", "notes"],
        "Cultivation": ["production_system", "crop_cycle_min", "crop_cycle_max", "cropping_system", "subsystem", "companion_species", "mechanization_level", "labour_intensity"],
    }

    def __init__(self,eco_crop_repo: EcoCropRepository):

        cultivation = eco_crop_repo.query_from_cultivation()
        crops = eco_crop_repo.query_from_crops()
        self.data: dict = cultivation | crops

    def print_crop(self, crop: dict):
        print("=" * 60)
        print(f"  {crop.get('common_name', 'Unknown').upper()}  ({crop.get('scientific_name', '')})")
        print("=" * 60)
        for section, fields in self.SECTIONS.items():
            print(f"\n  [{section}]")
            for field in fields:
                value = crop.get(field)
                if value is not None:
                    print(f"    {field:<22} {value}")
        print()

    def print_all(self):
        print(f"\n{'#' * 60}")
        print(f"  ECOCROP DATA — {len(self.data)} crop(s)")
        print(f"{'#' * 60}\n")
        for crop_data in self.data.values():
            self.print_crop(crop_data)


if __name__ == "__main__":
    EcoCropPrinter().print_all()
