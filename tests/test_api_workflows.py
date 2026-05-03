import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import create_app
from api.session import user_sessions


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

    def test_submit_input_resolves_smu_and_fao_context(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
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
                        "answers": {},
                    },
                )

        self.assertEqual(response.status_code, 200)
        session = user_sessions.get("u1")
        self.assertEqual(session["smu_id"], 31802)
        self.assertEqual(session["fao_90_class"], "Calcic Vertisols")

    def test_metadata_selections_exposes_frontend_dropdowns_and_questions(self):
        with self._build_client([]) as client:
            response = client.get("/metadata/selections")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertIn("user_input", payload)
        self.assertIn("crop_needs", payload)
        self.assertIn("fao_decision_questions", payload)
        self.assertEqual(payload["user_input"]["input_level"][0]["value"], "low")
        self.assertEqual(payload["crop_needs"]["texture_class"][0]["value"], "fine")
        self.assertEqual(payload["fao_decision_questions"][0]["id"], "water_context")

    def test_fao_decision_returns_next_question_for_multiple_candidates(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with self._build_client(
                [
                    {"fao_90": "Calcic Vertisols", "share": 40.0},
                    {"fao_90": "Calcaric Cambisols", "share": 30.0},
                    {"fao_90": "Calcic Luvisols", "share": 20.0},
                    {"fao_90": "Calcaric Fluvisols", "share": 10.0},
                ]
            ) as client:
                response = client.post(
                    "/soil/fao-decision",
                    json={"user_id": "u2", "coord": [36.8, 10.1], "answers": {}},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["status"], "question")
        self.assertEqual(payload["question"]["id"], "water_context")
        session = user_sessions.get("u2")
        self.assertEqual(session["smu_id"], 31802)
        self.assertNotIn("fao_90_class", session)

    def test_fao_decision_completes_for_single_candidate(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with self._build_client(
                [
                    {"fao_90": "Calcic Vertisols", "share": 100.0},
                ]
            ) as client:
                response = client.post(
                    "/soil/fao-decision",
                    json={"user_id": "u3", "coord": [36.8, 10.1], "answers": {}},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["selected_fao_90"], "Calcic Vertisols")
        session = user_sessions.get("u3")
        self.assertEqual(session["fao_90_class"], "Calcic Vertisols")

    def test_fao_decision_persists_selected_class_after_answers(self):
        with patch("api.services.resolve_smu_id", return_value=31802):
            with self._build_client(
                [
                    {"fao_90": "Calcic Vertisols", "share": 40.0},
                    {"fao_90": "Calcaric Cambisols", "share": 30.0},
                    {"fao_90": "Calcic Luvisols", "share": 20.0},
                    {"fao_90": "Calcaric Fluvisols", "share": 10.0},
                ]
            ) as client:
                response = client.post(
                    "/soil/fao-decision",
                    json={
                        "user_id": "u4",
                        "coord": [36.8, 10.1],
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
        session = user_sessions.get("u4")
        self.assertEqual(session["fao_90_class"], "Calcic Vertisols")
        self.assertEqual(session["answers"]["profile_development"], "Heavy clay that cracks open in summer")


if __name__ == "__main__":
    unittest.main()
