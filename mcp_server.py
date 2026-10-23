"""CloudForge diagnostic tools served over MCP Streamable HTTP."""

import os
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

import diagnostics


class ServiceHealthResult(BaseModel):
    """Current ECS service state."""

    model_config = ConfigDict(extra="forbid")

    service: str
    cluster: str
    status: str
    desired_tasks: int
    running_tasks: int
    pending_tasks: int
    deployment_state: str
    task_definition: str | None
    healthy: bool


class QueueStatusResult(BaseModel):
    """Approximate SQS backlog state."""

    model_config = ConfigDict(extra="forbid")

    queue: str
    messages_available: int
    messages_in_flight: int
    messages_delayed: int
    messages_total: int


class LogEvent(BaseModel):
    """One matching CloudWatch Logs event."""

    model_config = ConfigDict(extra="forbid")

    timestamp: int | None
    message: str
    log_stream: str | None
    event_id: str | None


class LogSearchResult(BaseModel):
    """Bounded CloudWatch Logs search results."""

    model_config = ConfigDict(extra="forbid")

    log_group: str
    query: str
    lookback_minutes: int
    matched_events: int
    events: list[LogEvent]


READ_ONLY = ToolAnnotations(read_only_hint=True)


def build_server(operations: Any = diagnostics) -> MCPServer:
    """Create the MCP server, optionally with injected diagnostic operations."""
    server = MCPServer(
        "cloudforge-diagnostics",
        version="0.1.0",
        instructions=(
            "Use these read-only tools to gather evidence from ECS, SQS, and "
            "CloudWatch before diagnosing the CloudForge orders incident."
        ),
    )

    @server.tool(
        description="Get desired, running, and pending task counts for one CloudForge ECS service.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_service_health(
        service_name: Annotated[
            str,
            Field(min_length=1, description="ECS service name, such as orders-worker."),
        ],
    ) -> ServiceHealthResult:
        return ServiceHealthResult.model_validate(
            operations.get_service_health(service_name),
        )

    @server.tool(
        description="Get approximate available, in-flight, delayed, and total messages for one SQS queue.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def get_queue_status(
        queue_name: Annotated[
            str,
            Field(min_length=1, description="SQS queue name, such as cloudforge-orders-queue."),
        ],
    ) -> QueueStatusResult:
        return QueueStatusResult.model_validate(
            operations.get_queue_status(queue_name),
        )

    @server.tool(
        description="Search recent CloudWatch logs for an exact text phrase, with bounded time and result limits.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def search_logs(
        log_group: Annotated[
            str,
            Field(min_length=1, description="CloudWatch log group name."),
        ],
        query: Annotated[
            str,
            Field(min_length=1, description="Exact text phrase to find."),
        ],
        lookback_minutes: Annotated[
            int,
            Field(ge=1, le=10_080, description="Minutes of history to search."),
        ] = 60,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of matching events."),
        ] = 20,
    ) -> LogSearchResult:
        return LogSearchResult.model_validate(
            operations.search_logs(
                log_group,
                query,
                lookback_minutes=lookback_minutes,
                limit=limit,
            ),
        )

    return server


mcp = build_server()


def main() -> None:
    """Run the server on the local Streamable HTTP endpoint."""
    host = os.environ.get("CLOUDFORGE_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("CLOUDFORGE_MCP_PORT", "8000"))
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        json_response=True,
    )


if __name__ == "__main__":
    main()
