"""API-level workflow tests covering session flow, metadata, and service wrappers."""
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from api.main import create_app
from api.session import user_sessions
from api.services import fetch_and_persist_external_lab_report, prepare_external_report_contract


class ApiWorkflowTests(unittest.TestCase):
    def setUp(self):
        user_sessions.clear()

    def tearDown(self):
        user_sessions.clear()

    def _build_client(self, candidates):
        fake_repos = SimpleNamespace(
            hwsd=SimpleNamespace(get_fao_90_candidates=lambda smu_id: candidates),
            ardhi=SimpleNamespace(),
            ecocrop=SimpleNamespace(),
        )
        app = create_app(repositories=fake_repos, lifespan_enabled=False)
        return TestClient(app)

    def test_calendar_get_reads_from_stored_user_session(self):
        fake_calendar_item = SimpleNamespace(
            to_dict=lambda: {
                "crop_code": "WHE",
                "planting_day": 120,
                "growth_days": 140,
                "planting_date": "April 29",
                "harvest_date": "September 16",
            }
        )
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with patch("api.services.CropCalendar") as mock_calendar:
                    mock_calendar.return_value.crop_calendar_class_factory.return_value = [fake_calendar_item]
                    with self._build_client([{"fao_90": "Calcic Vertisols", "share": 100.0}]) as client:
                        client.post(
                            "/submit-input",
                            json={
                                "user_id": "u-calendar",
                                "coord": [36.8, 10.1],
                                "input_level": "high",
                                "water_supply": "rainfed",
                            },
                        )
                        response = client.get("/calendar/u-calendar")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload[0]["crop_code"], "WHE")
        self.assertEqual(payload[0]["planting_day"], 120)

    def test_cors_headers_are_exposed_for_browser_clients(self):
        with self._build_client([]) as client:
            response = client.options(
                "/metadata/selections",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")

    def test_submit_input_resolves_smu_and_fao_context(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client(
                    [
                        {"fao_90": "Calcic Vertisols", "share": 60.0},
                        {"fao_90": "Calcaric Cambisols", "share": 40.0},
                    ]
                ) as client:
                    response = client.post(
                        "/submit-input",
                        json={
                            "user_id": "u1",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        session = user_sessions.get("u1")
        self.assertEqual(session["smu_id"], 31802)
        self.assertEqual(session["fao_90_class"], "Calcic Vertisols")
        self.assertEqual(session["ph_level"], "acidic")
        self.assertEqual(session["texture_class"], "fine")

    def test_submit_input_preserves_existing_user_context_fields(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client([{"fao_90": "Calcic Vertisols", "share": 100.0}]) as client:
                    client.post(
                        "/onboarding",
                        json={"user_id": "u-onboard", "lab_report_exists": True},
                    )
                    response = client.post(
                        "/submit-input",
                        json={
                            "user_id": "u-onboard",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(user_sessions.get("u-onboard")["lab_report_exists"])

    def test_submit_input_clears_irrigation_type_for_rainfed_requests(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client([{"fao_90": "Calcic Vertisols", "share": 100.0}]) as client:
                    response = client.post(
                        "/submit-input",
                        json={
                            "user_id": "u-rainfed",
                            "coord": [36.858096, 9.962084],
                            "input_level": "low",
                            "water_supply": "rainfed",
                            "irrigation_type": "drip",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(user_sessions.get("u-rainfed")["irrigation_type"])

    def test_submit_input_preserves_irrigated_sprinkler_in_session(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client([{"fao_90": "Calcic Vertisols", "share": 100.0}]) as client:
                    response = client.post(
                        "/submit-input",
                        json={
                            "user_id": "u-sprinkler",
                            "coord": [36.858096, 9.962084],
                            "input_level": "low",
                            "water_supply": "irrigated",
                            "irrigation_type": "sprinkler",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        session = user_sessions.get("u-sprinkler")
        self.assertEqual(session["water_supply"].value, "irrigated")
        self.assertEqual(session["irrigation_type"].value, "sprinkler")

    def test_metadata_selections_exposes_frontend_dropdowns_and_questions(self):
        with self._build_client([]) as client:
            response = client.get("/metadata/selections")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertIn("user_input", payload)
        self.assertEqual(payload["user_input"]["input_level"][0]["value"], "low")
        self.assertNotIn("crop_needs", payload)
        self.assertNotIn("fao_decision_questions", payload)

    def test_economic_suitability_endpoint_returns_revenue_metrics(self):
        with self._build_client([]) as client:
            response = client.post(
                "/economics/suitability",
                json={
                    "crop_name": "rice",
                    "crop_cost": 25.0,
                    "crop_yield": 2.0,
                    "farm_price": 343.0,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["crop_name"], "rice")
        self.assertEqual(payload["gross_revenue"], 686000.0)
        self.assertGreater(payload["net_revenue"], 0)
        self.assertLess(payload["net_revenue"], payload["gross_revenue"])
        self.assertEqual(payload["units"]["crop_cost"], "TND/ha")
        self.assertEqual(payload["units"]["farm_price"], "TND/kg")

    def test_lab_report_endpoint_saves_external_payload_to_json_file(self):
        temp_dir = Path("tests/.tmp/report-save-test")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        report_path = temp_dir / "rapport_values.json"

        try:
            with patch("api.services.REPORT_INPUT_PATH", report_path):
                with self._build_client([]) as client:
                    response = client.post(
                        "/lab-report",
                        json={
                            "user_id": "u-report",
                            "lab_report": {"report": [{"attribute": "pH", "value": 7.2}]},
                        },
                    )
                self.assertEqual(response.status_code, 200)
                payload = response.json()["data"]
                self.assertTrue(payload["lab_report_saved"])
                self.assertTrue(report_path.exists())
                saved = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["report"][0]["attribute"], "pH")
                session = user_sessions.get("u-report")
                self.assertEqual(session["lab_report_path"], str(report_path))
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_external_report_fetcher_can_persist_remote_payload(self):
        temp_dir = Path("tests/.tmp/external-fetch-test")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        report_path = temp_dir / "rapport_values.json"

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"report": {"report": [{"attribute": "OC", "value": 1.8}]}}

        contract = prepare_external_report_contract(
            url="https://service.local/report",
            auth=("user", "pass"),
            request_contract={
                "method": "POST",
                "headers": {"Authorization": "Bearer token"},
                "json_payload": {"user_id": "u-fetch"},
                "report_key": "report",
            },
        )

        try:
            with patch("api.services.REPORT_INPUT_PATH", report_path):
                with patch("api.services.requests.request", return_value=FakeResponse()) as mock_request:
                    result = fetch_and_persist_external_lab_report("u-fetch", contract)

                self.assertEqual(result["external_report_url"], "https://service.local/report")
                self.assertTrue(report_path.exists())
                saved = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["report"][0]["attribute"], "OC")
                session = user_sessions.get("u-fetch")
                self.assertEqual(session["lab_report_path"], str(report_path))
                self.assertEqual(mock_request.call_args.kwargs["method"], "POST")
                self.assertEqual(mock_request.call_args.kwargs["auth"], ("user", "pass"))
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_fao_get_questions_returns_next_question_for_multiple_candidates(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client(
                    [
                        {"fao_90": "Calcic Vertisols", "share": 40.0},
                        {"fao_90": "Calcaric Cambisols", "share": 30.0},
                        {"fao_90": "Calcic Luvisols", "share": 20.0},
                        {"fao_90": "Calcaric Fluvisols", "share": 10.0},
                    ]
                ) as client:
                    client.post(
                        "/submit-input",
                        json={
                            "user_id": "u2",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )
                    response = client.get("/fao-decision/get-questions/u2")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["smu_id"], 31802)
        self.assertEqual(payload["questions"][0]["id"], "water_context")
        self.assertGreaterEqual(len(payload["questions"]), 1)
        session = user_sessions.get("u2")
        self.assertEqual(session["smu_id"], 31802)
        self.assertEqual(len(session["fao_90_candidates"]), 4)

    def test_fao_get_questions_returns_candidates_and_no_questions_for_single_class(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client(
                    [
                        {"fao_90": "Calcic Vertisols", "share": 100.0},
                    ]
                ) as client:
                    client.post(
                        "/submit-input",
                        json={
                            "user_id": "u3",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )
                    response = client.get("/fao-decision/get-questions/u3")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["candidates"][0]["fao_90"], "Calcic Vertisols")
        self.assertEqual(payload["questions"], [])
        session = user_sessions.get("u3")
        self.assertEqual(session["smu_id"], 31802)

    def test_fao_post_answers_persists_selected_class_after_answers(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client(
                    [
                        {"fao_90": "Calcic Vertisols", "share": 40.0},
                        {"fao_90": "Calcaric Cambisols", "share": 30.0},
                        {"fao_90": "Calcic Luvisols", "share": 20.0},
                        {"fao_90": "Calcaric Fluvisols", "share": 10.0},
                    ]
                ) as client:
                    client.post(
                        "/submit-input",
                        json={
                            "user_id": "u4",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )
                    response = client.post(
                        "/fao-decision/post-answers",
                        json={
                            "user_id": "u4",
                            "answers": {
                                "water_context": "Dry land, no standing water",
                                "sodic_check": "No, it digs normally",
                                "arid_signature": "White chalky bits - lime",
                                "profile_development": "Heavy clay that cracks open in summer",
                            },
                        },
                    )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["selected_fao_90"], "Calcic Vertisols")
        self.assertEqual(payload["selected_fao_class"], "Calcic Vertisols")
        session = user_sessions.get("u4")
        self.assertEqual(session["fao_90_class"], "Calcic Vertisols")
        self.assertEqual(session["answers"]["profile_development"], "Heavy clay that cracks open in summer")

    def test_fao_post_answers_maps_question_number_keys_to_internal_ids(self):
        with patch("api.services.resolve_smu_id", return_value=31835):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client(
                    [
                        {"fao_90": "GLe", "share": 55.0},
                        {"fao_90": "VRk", "share": 25.0},
                        {"fao_90": "FLe", "share": 20.0},
                    ]
                ) as client:
                    client.post(
                        "/submit-input",
                        json={
                            "user_id": "u5",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )
                    questions_response = client.get("/fao-decision/get-questions/u5")
                    response = client.post(
                        "/fao-decision/post-answers",
                        json={
                            "user_id": "u5",
                            "answers": {
                                "question1": "Gets flooded by a river or wadi",
                            },
                        },
                    )

        self.assertEqual(questions_response.status_code, 200)
        self.assertEqual(questions_response.json()["data"]["questions"][0]["id"], "water_context")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user_sessions.get("u5")["answers"]["water_context"], "Gets flooded by a river or wadi")

    def test_fao_post_answers_maps_question_text_keys_to_internal_ids(self):
        with patch("api.services.resolve_smu_id", return_value=31835):
            with patch("api.services.derive_soil_selection", return_value={"ph_level": "acidic", "texture_class": "fine"}):
                with self._build_client(
                    [
                        {"fao_90": "GLe", "share": 55.0},
                        {"fao_90": "VRk", "share": 25.0},
                        {"fao_90": "FLe", "share": 20.0},
                    ]
                ) as client:
                    client.post(
                        "/submit-input",
                        json={
                            "user_id": "u6",
                            "coord": [36.8, 10.1],
                            "input_level": "high",
                            "water_supply": "rainfed",
                        },
                    )
                    client.get("/fao-decision/get-questions/u6")
                    response = client.post(
                        "/fao-decision/post-answers",
                        json={
                            "user_id": "u6",
                            "answers": {
                                "What's the water situation here?": "Wet most of the year, marshy or boggy",
                            },
                        },
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user_sessions.get("u6")["answers"]["water_context"], "Wet most of the year, marshy or boggy")


if __name__ == "__main__":
    unittest.main()
