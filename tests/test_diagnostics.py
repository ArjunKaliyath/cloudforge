"""Offline behavior tests for the bounded AWS diagnostic functions."""

import unittest
from unittest.mock import Mock

import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_service_health_reports_running_service(self):
        ecs = Mock()
        ecs.describe_services.return_value = {
            "services": [{
                "status": "ACTIVE",
                "desiredCount": 1,
                "runningCount": 1,
                "pendingCount": 0,
                "taskDefinition": "task-definition:2",
                "deployments": [{"status": "PRIMARY", "rolloutState": "COMPLETED"}],
            }],
            "failures": [],
        }

        result = diagnostics.get_service_health("orders-worker", ecs=ecs)

        self.assertTrue(result["healthy"])
        self.assertEqual(result["running_tasks"], 1)
        self.assertEqual(result["deployment_state"], "COMPLETED")
        ecs.describe_services.assert_called_once_with(
            cluster="cloudforge", services=["orders-worker"],
        )

    def test_service_health_reports_scaled_down_service_as_unhealthy(self):
        ecs = Mock()
        ecs.describe_services.return_value = {
            "services": [{
                "status": "ACTIVE",
                "desiredCount": 0,
                "runningCount": 0,
                "pendingCount": 0,
                "deployments": [{"status": "PRIMARY", "rolloutState": "COMPLETED"}],
            }],
        }

        result = diagnostics.get_service_health("orders-worker", ecs=ecs)

        self.assertFalse(result["healthy"])
        self.assertEqual(result["desired_tasks"], 0)

    def test_service_health_rejects_missing_service(self):
        ecs = Mock()
        ecs.describe_services.return_value = {
            "services": [],
            "failures": [{"arn": "orders-worker", "reason": "MISSING"}],
        }

        with self.assertRaisesRegex(LookupError, "MISSING"):
            diagnostics.get_service_health("orders-worker", ecs=ecs)

    def test_queue_status_converts_approximate_counts_to_numbers(self):
        sqs = Mock()
        sqs.get_queue_url.return_value = {"QueueUrl": "queue-url"}
        sqs.get_queue_attributes.return_value = {
            "Attributes": {
                "ApproximateNumberOfMessages": "5",
                "ApproximateNumberOfMessagesNotVisible": "2",
                "ApproximateNumberOfMessagesDelayed": "1",
            }
        }

        result = diagnostics.get_queue_status("cloudforge-orders-queue", sqs=sqs)

        self.assertEqual(result["messages_available"], 5)
        self.assertEqual(result["messages_in_flight"], 2)
        self.assertEqual(result["messages_delayed"], 1)
        self.assertEqual(result["messages_total"], 8)

    def test_log_search_is_bounded_and_returns_structured_events(self):
        paginator = Mock()
        paginator.paginate.return_value = [{
            "events": [{
                "timestamp": 1000,
                "message": "Database connection failed\n",
                "logStreamName": "ecs/orders-worker/task",
                "eventId": "event-1",
            }]
        }]
        logs = Mock()
        logs.get_paginator.return_value = paginator

        result = diagnostics.search_logs(
            "/ecs/cloudforge/orders-worker",
            "Database connection failed",
            logs=logs,
            lookback_minutes=15,
            limit=10,
            now_ms=1_000_000,
        )

        self.assertEqual(result["matched_events"], 1)
        self.assertEqual(result["events"][0]["message"], "Database connection failed")
        paginator.paginate.assert_called_once_with(
            logGroupName="/ecs/cloudforge/orders-worker",
            filterPattern='"Database connection failed"',
            startTime=100_000,
            endTime=1_000_000,
            interleaved=True,
            PaginationConfig={"MaxItems": 10, "PageSize": 10},
        )

    def test_log_search_rejects_unbounded_limit(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            diagnostics.search_logs("group", "error", logs=Mock(), limit=101)


if __name__ == "__main__":
    unittest.main()
