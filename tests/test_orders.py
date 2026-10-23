"""Offline behavior tests; SDK import doubles are scoped to loading orders."""

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


def load_orders():
    boto3 = ModuleType("boto3")
    botocore = ModuleType("botocore")
    exceptions = ModuleType("botocore.exceptions")
    exceptions.BotoCoreError = type("BotoCoreError", (Exception,), {})
    exceptions.ClientError = type("ClientError", (Exception,), {})
    spec = importlib.util.spec_from_file_location("orders", Path(__file__).parents[1] / "orders.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"boto3": boto3, "botocore": botocore, "botocore.exceptions": exceptions}):
        spec.loader.exec_module(module)
    return module


orders = load_orders()


class OrdersTests(unittest.TestCase):
    def test_success_deletes_using_receipt_handle(self):
        sqs = Mock()
        message = {"Body": '{"order_id": "1001"}', "ReceiptHandle": "receipt", "MessageId": "id"}
        with self.assertLogs("cloudforge.orders", level="INFO") as logs:
            self.assertTrue(orders.process_message(sqs, "queue-url", message))
        self.assertIn("Processed order_id=1001", logs.output[0])
        sqs.delete_message.assert_called_once_with(QueueUrl="queue-url", ReceiptHandle="receipt")

    def test_invalid_orders_are_never_deleted(self):
        for body in ("not-json", "[]", "{}", '{"order_id": ""}', '{"order_id": 1001}'):
            with self.subTest(body=body):
                sqs = Mock()
                with self.assertLogs("cloudforge.orders", level="ERROR"):
                    self.assertFalse(orders.process_message(sqs, "url", {"Body": body}))
                sqs.delete_message.assert_not_called()

    def test_delete_failure_is_not_reported_as_success(self):
        sqs = Mock()
        sqs.delete_message.side_effect = RuntimeError("request failed")
        with self.assertRaisesRegex(RuntimeError, "request failed"):
            orders.process_message(sqs, "url", {"Body": '{"order_id": "1001"}', "ReceiptHandle": "r"})

    def test_seed_produces_requested_orders(self):
        sqs = Mock()
        orders.seed_orders(sqs, "url", 3)
        bodies = [json.loads(call.kwargs["MessageBody"]) for call in sqs.send_message.call_args_list]
        self.assertEqual(bodies, [{"order_id": str(i)} for i in range(1001, 1004)])

    def test_once_handles_empty_receive(self):
        sqs = Mock()
        sqs.receive_message.return_value = {}
        self.assertEqual(orders.run_worker(sqs, "url", once=True), 0)
        sqs.receive_message.assert_called_once()
        sqs.delete_message.assert_not_called()

    def test_once_reports_failed_processing(self):
        sqs = Mock()
        sqs.receive_message.return_value = {"Messages": [{"Body": "bad-json"}]}
        with self.assertLogs("cloudforge.orders", level="ERROR"):
            self.assertEqual(orders.run_worker(sqs, "url", once=True), 1)
        sqs.delete_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
