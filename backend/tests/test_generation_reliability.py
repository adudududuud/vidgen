"""Regression tests for safe generation billing and refund accounting."""
import unittest
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.credit_record import CreditRecord, CreditType
from app.models.work import Work, WorkStatus
from app.routes.generation import _get_ready_workflow
from app.services.work_failed_service import mark_work_failed
from app.utils.internal_webhook import sign_generation_callback, verify_generation_callback, post_signed_generation_callback
from app.services.providers.gemini_provider import GeminiProvider


class WorkflowBillingGateTests(unittest.TestCase):
    def test_missing_workflow_is_rejected_before_any_work_is_created(self):
        db = MagicMock()
        workflow, error = _get_ready_workflow(db, SimpleNamespace(workflow_id=None))
        self.assertIsNone(workflow)
        self.assertIn("no workflow configured", error.lower())
        db.add.assert_not_called()

    def test_missing_workflow_record_is_rejected(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        workflow, error = _get_ready_workflow(db, SimpleNamespace(workflow_id=5))
        self.assertIsNone(workflow)
        self.assertIn("not found", error.lower())

    def test_workflow_without_api_nodes_is_rejected(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            nodes=[{"id": "input", "type": "prompt_input"}]
        )
        workflow, error = _get_ready_workflow(db, SimpleNamespace(workflow_id=5))
        self.assertIsNone(workflow)
        self.assertIn("no api", error.lower())

    def test_valid_workflow_is_accepted(self):
        db = MagicMock()
        expected = SimpleNamespace(nodes=[{"id": "api", "type": "api_call", "api_id": 7}])
        db.query.return_value.filter.return_value.first.return_value = expected
        workflow, error = _get_ready_workflow(db, SimpleNamespace(workflow_id=5))
        self.assertIs(workflow, expected)
        self.assertIsNone(error)


class RefundLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.work = SimpleNamespace(id=81, user_id=17, status=WorkStatus.GENERATING,
                                    error_message=None, completed_at=None)
        self.work_query = MagicMock()
        self.credit_query = MagicMock()
        self.work_query.filter.return_value.with_for_update.return_value.first.return_value = self.work
        self.db.query.side_effect = lambda model: (
            self.work_query if model is Work else self.credit_query
        )

    @patch("app.services.work_failed_service.credit_service_add_credits")
    def test_refund_is_exact_amount_from_consumption_ledger(self, add_credits):
        self.credit_query.filter.return_value.first.return_value = None
        self.credit_query.filter.return_value.all.return_value = [
            SimpleNamespace(amount=-37),
        ]
        mark_work_failed(self.db, self.work, "Provider failed")
        self.assertEqual(self.work.status, WorkStatus.FAILED)
        args = add_credits.call_args.args
        self.assertEqual(args[1:4], (17, 37, CreditType.REFUND))
        self.assertEqual(add_credits.call_args.kwargs["work_id"], 81)
        self.work_query.filter.return_value.with_for_update.assert_called_once()

    @patch("app.services.work_failed_service.credit_service_add_credits")
    def test_duplicate_refund_is_skipped(self, add_credits):
        self.credit_query.filter.return_value.first.return_value = SimpleNamespace(id=2)
        mark_work_failed(self.db, self.work, "Second callback")
        add_credits.assert_not_called()

    @patch("app.services.work_failed_service.credit_service_add_credits")
    def test_no_charge_means_no_refund(self, add_credits):
        self.credit_query.filter.return_value.first.return_value = None
        self.credit_query.filter.return_value.all.return_value = []
        mark_work_failed(self.db, self.work, "Validation failure")
        add_credits.assert_not_called()

    @patch("app.services.work_failed_service.credit_service_add_credits")
    def test_late_failure_cannot_refund_successful_job(self, add_credits):
        self.work.status = WorkStatus.SUCCESS
        mark_work_failed(self.db, self.work, "Late callback")
        add_credits.assert_not_called()



class SignedGenerationCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_body_work_id_and_node_id_are_authenticated(self):
        with patch.dict(os.environ, {"VIDGEN_WEBHOOK_SECRET": "v0.1-test-only-secret"}):
            body = b'{"status":"succeeded","id":"task1"}'
            signature = sign_generation_callback(81, body, "node-1")
            self.assertTrue(verify_generation_callback(81, body, signature, "node-1"))
            self.assertFalse(verify_generation_callback(82, body, signature, "node-1"))
            self.assertFalse(verify_generation_callback(81, body, signature, "node-2"))
            self.assertFalse(verify_generation_callback(81, b'{"status":"failed"}', signature, "node-1"))
            self.assertFalse(verify_generation_callback(81, body, None, "node-1"))

    async def test_signed_sender_matches_receiver(self):
        with patch.dict(os.environ, {"VIDGEN_WEBHOOK_SECRET": "v0.1-test-only-secret"}):
            client = MagicMock()
            from unittest.mock import AsyncMock
            client.post = AsyncMock()
            url = "http://backend:8000/api/webhook/replicate/81?node_id=img"
            await post_signed_generation_callback(
                client, url, 81, {"status": "succeeded", "output": "测试"}
            )
            args, kwargs = client.post.await_args
            self.assertEqual(args[0], url)
            self.assertTrue(verify_generation_callback(
                81, kwargs["content"], kwargs["headers"]["X-VidGen-Signature"], "img"
            ))



class GeminiWorkflowResultTests(unittest.TestCase):
    @patch("app.services.providers.gemini_provider.set_json", return_value=True)
    def test_result_is_written_to_shared_redis(self, set_json):
        provider = GeminiProvider()
        provider._store_result("gemini_123", {"status": "success", "text": "hello"})
        set_json.assert_called_once_with(
            "gemini:workflow-result:gemini_123",
            {"status": "success", "text": "hello"},
            ttl_seconds=3600,
        )
        self.assertEqual(provider._result_cache, {})

    @patch("app.services.providers.gemini_provider.get_json")
    def test_separate_api_process_reads_worker_result(self, get_json):
        get_json.return_value = {"status": "success", "text": "shared"}
        api_provider = GeminiProvider()
        self.assertEqual(
            api_provider._load_result("gemini_123"),
            {"status": "success", "text": "shared"},
        )

    @patch("app.services.providers.gemini_provider.set_json", return_value=False)
    def test_production_requires_shared_cache(self, _set_json):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with self.assertRaisesRegex(RuntimeError, "Redis is required"):
                GeminiProvider()._store_result("gemini_123", {"status": "success"})


if __name__ == "__main__":
    unittest.main()
