import unittest

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import AugmentedLayer, AugmentedLayersGroup, pH_level
from engines.soil_FAO_decision import classify_soil_dynamic, get_next_question
from engines.soil_properties_builder.hwsd2_prop.hwsd_prop_generator import augmented_layers_group_to_dict
from engines.soil_properties_builder.report_augmentation.processing import ReportOperations
import sqlite3


class SoilPropertyContractTests(unittest.TestCase):
    def test_augmented_layers_group_to_dict_keys_by_layer(self):
        group = AugmentedLayersGroup(
            [
                AugmentedLayer(layer="D1", smu_id=31802, values={"pH": 7.4, "TXT": "clay"}),
                AugmentedLayer(layer="D2", smu_id=31802, values={"pH": 7.8, "TXT": "loam"}),
            ]
        )

        self.assertEqual(
            augmented_layers_group_to_dict(group),
            {
                "D1": {"smu_id": 31802, "pH": 7.4, "TXT": "clay"},
                "D2": {"smu_id": 31802, "pH": 7.8, "TXT": "loam"},
            },
        )

    def test_report_ph_classification(self):
        acidic_report = [{"attribute": "pH", "value": 6.5}]
        basic_report = [{"attribute": "pH", "value": 8.1}]

        self.assertEqual(ReportOperations(acidic_report).get_report_ph_class(), pH_level.ACIDIC)
        self.assertEqual(ReportOperations(basic_report).get_report_ph_class(), pH_level.BASIC)

    def test_fao_decision_exposes_next_dynamic_question(self):
        smu_input = {
            "Calcic Vertisols": 0.40,
            "Calcaric Cambisols": 0.30,
            "Calcic Luvisols": 0.20,
            "Calcaric Fluvisols": 0.10,
        }

        next_question = get_next_question(smu_input, {})
        self.assertIsNotNone(next_question)
        self.assertEqual(next_question["id"], "water_context")

    def test_fao_decision_completes_from_partial_answers(self):
        smu_input = {
            "Calcic Vertisols": 0.40,
            "Calcaric Cambisols": 0.30,
            "Calcic Luvisols": 0.20,
            "Calcaric Fluvisols": 0.10,
        }
        answers = {
            "water_context": "Dry land, no standing water",
            "sodic_check": "No, it digs normally",
            "arid_signature": "White chalky bits - lime",
            "profile_development": "Heavy clay that cracks open in summer",
        }

        result = classify_soil_dynamic(smu_input, answers)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["selected_soil"], "Calcic Vertisols")

    def test_hwsd_repo_returns_fao_candidates_sorted_by_share(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE HWSD2_SMU (HWSD2_SMU_ID INTEGER, FAO90 TEXT, SHARE REAL)")
        conn.execute("INSERT INTO HWSD2_SMU VALUES (1, 'Class B', 40)")
        conn.execute("INSERT INTO HWSD2_SMU VALUES (1, 'Class A', 60)")
        repo = HwsdRepository(conn)

        candidates = repo.get_fao_90_candidates(1)

        self.assertEqual(
            candidates,
            [
                {"fao_90": "Class A", "share": 60.0},
                {"fao_90": "Class B", "share": 40.0},
            ],
        )
        conn.close()

    def test_ardhi_repo_optional_irrigation_queries_preserve_null_logic(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE tiff_files (
                crop_code TEXT,
                map_code TEXT,
                input_level TEXT,
                water_supply TEXT,
                irrigation_type TEXT,
                file_path TEXT,
                sq_factor TEXT,
                management TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tiff_files (crop_code, map_code, input_level, water_supply, irrigation_type, file_path)
            VALUES ('WHE', 'RES05-SXX30AS', 'high', 'irrigated', NULL, 'rainfed-default.tif')
            """
        )
        conn.execute(
            """
            INSERT INTO tiff_files (crop_code, map_code, input_level, water_supply, irrigation_type, file_path)
            VALUES ('WHE', 'RES05-SXX30AS', 'high', 'irrigated', 'drip', 'drip-only.tif')
            """
        )
        repo = ArdhiRepository(conn)

        default_path = repo.query_tiff_path("high", "irrigated", "WHE", "RES05-SXX30AS")
        drip_path = repo.query_tiff_path("high", "irrigated", "WHE", "RES05-SXX30AS", "drip")

        self.assertEqual(default_path, "rainfed-default.tif")
        self.assertEqual(drip_path, "drip-only.tif")
        conn.close()


if __name__ == "__main__":
    unittest.main()
