"""Run the CloudForge incident investigator with Strands and Amazon Bedrock."""

import argparse
import logging
import sys
from typing import Any

import boto3
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient


DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_MODEL_ID = "amazon.nova-micro-v1:0"
DEFAULT_QUESTION = "Why are orders delayed?"
MAX_TOKENS_PER_TURN = 600
MAX_INVOCATION_OUTPUT_TOKENS = 2_400
MAX_TURNS = 5
ALLOWED_TOOLS = ["get_service_health", "get_queue_status", "search_logs"]
LOGGER = logging.getLogger("cloudforge.agent")

SYSTEM_PROMPT = """You are the CloudForge incident investigator.

Gather evidence before reaching a conclusion. Use only the supplied read-only
MCP tools for AWS infrastructure state, and never invent state that a tool did
not return. Clearly separate observed evidence from your likely diagnosis.
Recommend a safe remediation, but never execute remediation or destructive
actions.

For an orders-delay investigation, call all three tools before answering:
1. get_service_health with service_name "orders-worker"
2. get_queue_status with queue_name "cloudforge-orders-queue"
3. search_logs with log_group "/ecs/cloudforge/orders-worker", query
   "Database connection failed", lookback_minutes 10080, and limit 20

Explain the ECS worker state, the SQS backlog, and matching CloudWatch errors in
a concise diagnosis suitable for someone new to AWS.
"""


def build_bedrock_model(
    *,
    profile: str | None,
    region: str,
    model_id: str = DEFAULT_MODEL_ID,
) -> BedrockModel:
    """Create the bounded Bedrock model used by the Strands agent."""
    session = boto3.Session(profile_name=profile, region_name=region)
    return BedrockModel(
        boto_session=session,
        model_id=model_id,
        max_tokens=MAX_TOKENS_PER_TURN,
        temperature=0.0,
        streaming=False,
    )


def build_agent(*, model: Any, mcp_url: str = DEFAULT_MCP_URL) -> Agent:
    """Create one agent whose AWS diagnostic access is limited to MCP."""
    mcp_client = MCPClient(
        url=mcp_url,
        tool_filters={"allowed": ALLOWED_TOOLS},
        application_name="cloudforge-incident-agent",
        application_version="0.1.0",
    )
    return Agent(
        model=model,
        tools=[mcp_client],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
        name="cloudforge-incident-investigator",
        description="Investigates the CloudForge orders-delay demo through MCP.",
    )


def investigate(
    question: str,
    *,
    profile: str | None,
    region: str,
    mcp_url: str = DEFAULT_MCP_URL,
    model_id: str = DEFAULT_MODEL_ID,
) -> Any:
    """Ask the agent one bounded incident-investigation question."""
    if not question.strip():
        raise ValueError("question must not be empty")

    model = build_bedrock_model(profile=profile, region=region, model_id=model_id)
    agent = build_agent(model=model, mcp_url=mcp_url)
    return agent(
        question,
        limits={
            "turns": MAX_TURNS,
            "output_tokens": MAX_INVOCATION_OUTPUT_TOKENS,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--profile")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    args = parser.parse_args()

    try:
        result = investigate(
            args.question,
            profile=args.profile,
            region=args.region,
            mcp_url=args.mcp_url,
            model_id=args.model_id,
        )
    except Exception as error:
        LOGGER.error("Incident investigation failed: %s", error)
        return 1

    print(str(result))
    tools_used = sorted(result.metrics.tool_metrics)
    print(f"\nTools used: {', '.join(tools_used) if tools_used else 'none'}")
    print(f"Model turns: {result.metrics.cycle_count}")
    usage = result.metrics.accumulated_usage
    print(
        "Tokens: "
        f"input={usage['inputTokens']}, "
        f"output={usage['outputTokens']}, "
        f"total={usage['totalTokens']}"
    )
    print(f"Stop reason: {result.stop_reason}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
