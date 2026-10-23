"""Read-only AWS diagnostics for the CloudForge incident workflow."""

import argparse
import json
import logging
import sys
import time
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_CLUSTER = "cloudforge"
DEFAULT_LOOKBACK_MINUTES = 60
DEFAULT_LOG_LIMIT = 20
LOGGER = logging.getLogger("cloudforge.diagnostics")


def get_service_health(
    service_name: str,
    *,
    ecs: Any | None = None,
    cluster_name: str = DEFAULT_CLUSTER,
) -> dict[str, Any]:
    """Return the desired and running state of one ECS service."""
    if not service_name.strip():
        raise ValueError("service_name must not be empty")
    if not cluster_name.strip():
        raise ValueError("cluster_name must not be empty")

    client = ecs or boto3.client("ecs")
    response = client.describe_services(cluster=cluster_name, services=[service_name])
    services = response.get("services", [])
    failures = response.get("failures", [])
    if failures or not services:
        reason = failures[0].get("reason", "service not found") if failures else "service not found"
        raise LookupError(f"ECS service {service_name!r} was not found: {reason}")

    service = services[0]
    desired = int(service.get("desiredCount", 0))
    running = int(service.get("runningCount", 0))
    pending = int(service.get("pendingCount", 0))
    status = service.get("status", "UNKNOWN")
    deployments = service.get("deployments", [])
    primary = next(
        (deployment for deployment in deployments if deployment.get("status") == "PRIMARY"),
        deployments[0] if deployments else {},
    )
    rollout_state = primary.get("rolloutState", "UNKNOWN")
    healthy = (
        status == "ACTIVE"
        and desired > 0
        and running >= desired
        and pending == 0
        and rollout_state != "FAILED"
    )

    return {
        "service": service_name,
        "cluster": cluster_name,
        "status": status,
        "desired_tasks": desired,
        "running_tasks": running,
        "pending_tasks": pending,
        "deployment_state": rollout_state,
        "task_definition": service.get("taskDefinition"),
        "healthy": healthy,
    }


def get_queue_status(queue_name: str, *, sqs: Any | None = None) -> dict[str, Any]:
    """Return approximate available, in-flight, and delayed SQS counts."""
    if not queue_name.strip():
        raise ValueError("queue_name must not be empty")

    client = sqs or boto3.client("sqs")
    queue_url = client.get_queue_url(QueueName=queue_name)["QueueUrl"]
    response = client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
        ],
    )
    attributes = response.get("Attributes", {})
    available = int(attributes.get("ApproximateNumberOfMessages", 0))
    in_flight = int(attributes.get("ApproximateNumberOfMessagesNotVisible", 0))
    delayed = int(attributes.get("ApproximateNumberOfMessagesDelayed", 0))

    return {
        "queue": queue_name,
        "messages_available": available,
        "messages_in_flight": in_flight,
        "messages_delayed": delayed,
        "messages_total": available + in_flight + delayed,
    }


def search_logs(
    log_group: str,
    query: str,
    *,
    logs: Any | None = None,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
    limit: int = DEFAULT_LOG_LIMIT,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Find recent CloudWatch log events containing an exact text phrase."""
    if not log_group.strip():
        raise ValueError("log_group must not be empty")
    if not query.strip():
        raise ValueError("query must not be empty")
    if lookback_minutes < 1:
        raise ValueError("lookback_minutes must be at least 1")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    client = logs or boto3.client("logs")
    end_time = now_ms if now_ms is not None else int(time.time() * 1000)
    start_time = end_time - lookback_minutes * 60 * 1000
    events: list[dict[str, Any]] = []
    paginator = client.get_paginator("filter_log_events")
    pages = paginator.paginate(
        logGroupName=log_group,
        filterPattern=json.dumps(query),
        startTime=start_time,
        endTime=end_time,
        interleaved=True,
        PaginationConfig={"MaxItems": limit, "PageSize": limit},
    )
    for page in pages:
        for event in page.get("events", []):
            events.append(
                {
                    "timestamp": event.get("timestamp"),
                    "message": event.get("message", "").rstrip("\r\n"),
                    "log_stream": event.get("logStreamName"),
                    "event_id": event.get("eventId"),
                }
            )

    return {
        "log_group": log_group,
        "query": query,
        "lookback_minutes": lookback_minutes,
        "matched_events": len(events),
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--region")
    commands = parser.add_subparsers(dest="command", required=True)

    service = commands.add_parser("service", help="Inspect one ECS service")
    service.add_argument("service_name")
    service.add_argument("--cluster", default=DEFAULT_CLUSTER)

    queue = commands.add_parser("queue", help="Inspect one SQS queue")
    queue.add_argument("queue_name")

    logs = commands.add_parser("logs", help="Search recent CloudWatch logs")
    logs.add_argument("log_group")
    logs.add_argument("query")
    logs.add_argument("--lookback-minutes", type=int, default=DEFAULT_LOOKBACK_MINUTES)
    logs.add_argument("--limit", type=int, default=DEFAULT_LOG_LIMIT)

    args = parser.parse_args()
    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        if args.command == "service":
            result = get_service_health(
                args.service_name,
                ecs=session.client("ecs"),
                cluster_name=args.cluster,
            )
        elif args.command == "queue":
            result = get_queue_status(args.queue_name, sqs=session.client("sqs"))
        else:
            result = search_logs(
                args.log_group,
                args.query,
                logs=session.client("logs"),
                lookback_minutes=args.lookback_minutes,
                limit=args.limit,
            )
        print(json.dumps(result, indent=2))
        return 0
    except (BotoCoreError, ClientError, LookupError, ValueError) as error:
        LOGGER.error("Diagnostic request failed: %s", error)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
