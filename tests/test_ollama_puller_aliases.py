import unittest
from unittest.mock import MagicMock, patch
import json
import time

from src.model_engines.ollama_model_puller import (
    MODEL_PULL_ALIASES,
    REVERSE_MODEL_ALIASES,
    pull_ollama_model,
    delete_ollama_model,
    test_ollama_translation as run_test_ollama_translation,
    get_ollama_models_details,
)
from src.model_engines.ollama_manifest_scanner import scan_local_manifests, invalidate_manifests_cache


class TestOllamaPullerAliases(unittest.TestCase):
    def test_alias_mappings_exist(self):
        self.assertIn("amadeus:7b", MODEL_PULL_ALIASES)
        self.assertIn("amadeus:14b", MODEL_PULL_ALIASES)
        self.assertIn("amadeus:32b", MODEL_PULL_ALIASES)
        self.assertTrue(MODEL_PULL_ALIASES["amadeus:14b"].startswith("hf.co/mradermacher/"))

    def test_pull_ollama_model_resolves_alias_and_calls_copy(self):
        mock_mgr = MagicMock()
        downloads = {}
        mock_mgr._get_downloads.return_value = downloads
        mock_mgr._get_lock.return_value = MagicMock()
        mock_mgr._completed_models = set()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            json.dumps({"status": "pulling manifest"}).encode("utf-8"),
            json.dumps({"status": "success"}).encode("utf-8"),
        ]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        mock_copy_resp = MagicMock()
        mock_copy_resp.status_code = 200

        mock_session = MagicMock()
        mock_session.post.side_effect = lambda url, **kwargs: (
            mock_copy_resp if "/copy" in url else mock_resp
        )
        mock_session.delete.return_value = MagicMock(status_code=200)

        res = pull_ollama_model(mock_mgr, "amadeus:14b", session_factory=lambda: mock_session)
        self.assertTrue(res["success"])

        # Wait for thread to finish
        time.sleep(0.3)

        # Check that post was called with target_remote_name
        post_calls = mock_session.post.call_args_list
        self.assertTrue(len(post_calls) >= 1)
        first_call = post_calls[0]
        self.assertIn("name", first_call.kwargs.get("json", {}))
        self.assertEqual(
            first_call.kwargs["json"]["name"],
            MODEL_PULL_ALIASES["amadeus:14b"],
        )

    def test_delete_ollama_model_cleans_both_names(self):
        mock_mgr = MagicMock()
        mock_mgr._get_downloads.return_value = {}
        mock_mgr._get_lock.return_value = MagicMock()
        mock_mgr._completed_models = {"amadeus:14b"}

        mock_session = MagicMock()
        mock_session.delete.return_value = MagicMock(status_code=200)

        res = delete_ollama_model(mock_mgr, "amadeus:14b", session_factory=lambda: mock_session)
        self.assertTrue(res["success"])

        deleted_models = [call.kwargs["json"]["name"] for call in mock_session.delete.call_args_list]
        self.assertIn("amadeus:14b", deleted_models)
        self.assertIn(MODEL_PULL_ALIASES["amadeus:14b"], deleted_models)

    def test_test_ollama_translation_falls_back_to_alias(self):
        mock_mgr = MagicMock()
        mock_resp_404 = MagicMock(status_code=404, text="Model not found")
        mock_resp_200 = MagicMock(status_code=200)
        mock_resp_200.json.return_value = {
            "response": "Segure firme!",
            "eval_count": 10,
            "eval_duration": 1000000000,
        }

        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_resp_404, mock_resp_200]

        res = run_test_ollama_translation(mock_mgr, "amadeus:14b", session_factory=lambda: mock_session)
        self.assertTrue(res["success"])
        self.assertEqual(res["translation"], "Segure firme!")

    def test_get_ollama_models_details_mirrors_alias(self):
        mock_mgr = MagicMock()
        mock_mgr._tags_cache_data = {
            "models": [
                {
                    "name": MODEL_PULL_ALIASES["amadeus:14b"],
                    "size": 9000000000,
                }
            ]
        }

        details = get_ollama_models_details(mock_mgr)
        self.assertIn(MODEL_PULL_ALIASES["amadeus:14b"], details)
        self.assertIn("amadeus:14b", details)
        self.assertEqual(details["amadeus:14b"]["size"], 9000000000)
