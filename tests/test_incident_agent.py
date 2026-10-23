"""Offline tests for the CloudForge Strands agent wiring."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import incident_agent


class IncidentAgentTests(unittest.TestCase):
    @patch("incident_agent.BedrockModel")
    @patch("incident_agent.boto3.Session")
    def test_bedrock_model_is_low_cost_and_bounded(self, session, bedrock_model):
        session_instance = session.return_value

        result = incident_agent.build_bedrock_model(
            profile="arjun",
            region="us-east-1",
        )

        session.assert_called_once_with(profile_name="arjun", region_name="us-east-1")
        bedrock_model.assert_called_once_with(
            boto_session=session_instance,
            model_id="amazon.nova-micro-v1:0",
            max_tokens=600,
            temperature=0.0,
            streaming=False,
        )
        self.assertIs(result, bedrock_model.return_value)

    @patch("incident_agent.Agent")
    @patch("incident_agent.MCPClient")
    def test_agent_receives_only_the_three_mcp_tools(self, mcp_client, agent):
        model = object()

        result = incident_agent.build_agent(model=model)

        mcp_client.assert_called_once_with(
            url="http://127.0.0.1:8000/mcp",
            tool_filters={
                "allowed": [
                    "get_service_health",
                    "get_queue_status",
                    "search_logs",
                ],
            },
            application_name="cloudforge-incident-agent",
            application_version="0.1.0",
        )
        agent.assert_called_once()
        call = agent.call_args.kwargs
        self.assertEqual(call["tools"], [mcp_client.return_value])
        self.assertIs(call["model"], model)
        self.assertIn("call all three tools", call["system_prompt"])
        self.assertIn("never invent state", call["system_prompt"])
        self.assertIs(result, agent.return_value)

    @patch("incident_agent.build_agent")
    @patch("incident_agent.build_bedrock_model")
    def test_investigation_applies_per_invocation_limits(self, model_builder, agent_builder):
        fake_agent = Mock(return_value=SimpleNamespace())
        agent_builder.return_value = fake_agent

        incident_agent.investigate(
            "Why are orders delayed?",
            profile="arjun",
            region="us-east-1",
        )

        fake_agent.assert_called_once_with(
            "Why are orders delayed?",
            limits={"turns": 5, "output_tokens": 2_400},
        )

    def test_empty_question_is_rejected_before_model_call(self):
        with self.assertRaisesRegex(ValueError, "question must not be empty"):
            incident_agent.investigate("   ", profile="arjun", region="us-east-1")


if __name__ == "__main__":
    unittest.main()
