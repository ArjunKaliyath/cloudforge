"""In-memory MCP client tests for the CloudForge server."""

from types import SimpleNamespace
import unittest

from mcp import Client

import mcp_server


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_lists_and_calls_all_three_structured_tools(self):
        operations = SimpleNamespace(
            get_service_health=lambda service_name: {
                "service": service_name,
                "cluster": "cloudforge",
                "status": "ACTIVE",
                "desired_tasks": 0,
                "running_tasks": 0,
                "pending_tasks": 0,
                "deployment_state": "COMPLETED",
                "task_definition": "task-definition:2",
                "healthy": False,
            },
            get_queue_status=lambda queue_name: {
                "queue": queue_name,
                "messages_available": 5,
                "messages_in_flight": 0,
                "messages_delayed": 0,
                "messages_total": 5,
            },
            search_logs=lambda log_group, query, **kwargs: {
                "log_group": log_group,
                "query": query,
                "lookback_minutes": kwargs["lookback_minutes"],
                "matched_events": 1,
                "events": [{
                    "timestamp": 1000,
                    "message": "Database connection failed",
                    "log_stream": "ecs/orders-worker/task",
                    "event_id": "event-1",
                }],
            },
        )
        server = mcp_server.build_server(operations)

        async with Client(server) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            self.assertEqual(
                set(tools),
                {"get_service_health", "get_queue_status", "search_logs"},
            )
            for tool in tools.values():
                self.assertTrue(tool.annotations.read_only_hint)
                self.assertIsNotNone(tool.output_schema)

            service = await client.call_tool(
                "get_service_health", {"service_name": "orders-worker"},
            )
            queue = await client.call_tool(
                "get_queue_status", {"queue_name": "cloudforge-orders-queue"},
            )
            logs = await client.call_tool(
                "search_logs",
                {
                    "log_group": "/ecs/cloudforge/orders-worker",
                    "query": "Database connection failed",
                    "lookback_minutes": 180,
                    "limit": 10,
                },
            )

        self.assertFalse(service.is_error)
        self.assertEqual(service.structured_content["desired_tasks"], 0)
        self.assertFalse(service.structured_content["healthy"])
        self.assertFalse(queue.is_error)
        self.assertEqual(queue.structured_content["messages_total"], 5)
        self.assertFalse(logs.is_error)
        self.assertEqual(logs.structured_content["matched_events"], 1)

    async def test_client_rejects_out_of_bounds_log_limit(self):
        server = mcp_server.build_server(SimpleNamespace())

        async with Client(server) as client:
            result = await client.call_tool(
                "search_logs",
                {"log_group": "group", "query": "error", "limit": 101},
            )

        self.assertTrue(result.is_error)


if __name__ == "__main__":
    unittest.main()
