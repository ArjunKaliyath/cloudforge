"""Offline tests for the CloudForge FastAPI boundary."""

from types import SimpleNamespace
import unittest

from fastapi.testclient import TestClient

import api


def successful_result() -> SimpleNamespace:
    metrics = SimpleNamespace(
        tool_metrics={
            "get_service_health": object(),
            "get_queue_status": object(),
            "search_logs": object(),
        },
        cycle_count=2,
        accumulated_usage={
            "inputTokens": 1200,
            "outputTokens": 300,
            "totalTokens": 1500,
        },
    )
    return SimpleNamespace(
        metrics=metrics,
        stop_reason="end_turn",
        __str__=lambda self: "unused",
    )


class PrintableResult:
    def __init__(self):
        source = successful_result()
        self.metrics = source.metrics
        self.stop_reason = source.stop_reason

    def __str__(self) -> str:
        return "<thinking>hidden work</thinking>\nOrders are delayed because no worker is running."


class APITests(unittest.TestCase):
    def test_investigation_returns_diagnosis_and_execution_evidence(self):
        calls: list[tuple[str, dict[str, str | None]]] = []

        def investigator(question: str, **kwargs):
            calls.append((question, kwargs))
            return PrintableResult()

        with TestClient(api.create_app(investigator)) as client:
            response = client.post(
                "/api/investigate",
                json={"question": "Why are orders delayed?"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["diagnosis"], "Orders are delayed because no worker is running.")
        self.assertEqual(
            body["tools_used"],
            ["get_queue_status", "get_service_health", "search_logs"],
        )
        self.assertEqual(body["model_turns"], 2)
        self.assertEqual(body["tokens"], {"input": 1200, "output": 300, "total": 1500})
        self.assertEqual(calls[0][0], "Why are orders delayed?")

    def test_empty_question_is_rejected(self):
        with TestClient(api.create_app()) as client:
            response = client.post("/api/investigate", json={"question": ""})

        self.assertEqual(response.status_code, 422)

    def test_agent_failure_becomes_gateway_error(self):
        def failing_investigator(*args, **kwargs):
            raise RuntimeError("MCP unavailable")

        with TestClient(api.create_app(failing_investigator)) as client:
            response = client.post(
                "/api/investigate",
                json={"question": "Why are orders delayed?"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("MCP unavailable", response.text)


if __name__ == "__main__":
    unittest.main()
