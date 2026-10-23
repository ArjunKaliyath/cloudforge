"""Create and seed the demo SQS queue, or run its local orders worker."""

import argparse
import json
import logging
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

QUEUE_NAME = "cloudforge-orders-queue"
LOGGER = logging.getLogger("cloudforge.orders")


def create_queue(sqs: Any) -> str:
    """Create the standard demo queue, or reuse it with matching attributes."""
    response = sqs.create_queue(
        QueueName=QUEUE_NAME,
        Attributes={"ReceiveMessageWaitTimeSeconds": "20", "VisibilityTimeout": "30"},
    )
    return response["QueueUrl"]


def seed_orders(sqs: Any, queue_url: str, count: int) -> None:
    for index in range(count):
        order_id = str(1001 + index)
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps({"order_id": order_id}))
        LOGGER.info("Seeded order_id=%s", order_id)


def process_message(sqs: Any, queue_url: str, message: dict[str, Any]) -> bool:
    """Acknowledge valid demo orders only after processing succeeds."""
    try:
        order = json.loads(message["Body"])
        if not isinstance(order, dict):
            raise ValueError("Expected a JSON object")
        order_id = order.get("order_id")
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("Expected a nonempty string order_id")
    except (ValueError, KeyError):
        LOGGER.exception("Invalid order message_id=%s; leaving message in queue", message.get("MessageId"))
        return False

    if os.environ.get("BROKEN_MODE", "false").strip().lower() == "true":
        LOGGER.error("Database connection failed order_id=%s; leaving message in queue (BROKEN_MODE=true)", order_id)
        return False

    # The MVP's processing operation is logging the order ID.
    LOGGER.info("Processed order_id=%s", order_id)
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
    return True


def run_worker(sqs: Any, queue_url: str, once: bool = False) -> int:
    """Long-poll until interrupted; --once handles one receive request."""
    failures = 0
    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20,
        )
        for message in response.get("Messages", []):
            if not process_message(sqs, queue_url, message):
                failures += 1
        if once:
            return 1 if failures else 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create", help="Create the demo SQS queue")
    seed = commands.add_parser("seed", help="Send example orders to the existing queue")
    seed.add_argument("--count", type=int, default=5)
    worker = commands.add_parser("worker", help="Process orders until Ctrl+C")
    worker.add_argument("--once", action="store_true", help="Handle one receive request, then exit")
    commands.add_parser("status", help="Show approximate queued and in-flight message counts")
    args = parser.parse_args()
    if args.command == "seed" and args.count < 1:
        parser.error("--count must be at least 1")

    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        sqs = session.client("sqs")
        if args.command == "create":
            print(create_queue(sqs))
            return 0
        queue_url = sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
        if args.command == "seed":
            seed_orders(sqs, queue_url, args.count)
        elif args.command == "worker":
            return run_worker(sqs, queue_url, args.once)
        else:
            response = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible", "ApproximateNumberOfMessagesDelayed"],
            )
            print(json.dumps(response["Attributes"], indent=2))
        return 0
    except (BotoCoreError, ClientError) as error:
        LOGGER.error("AWS request failed: %s", error)
        return 1
    except KeyboardInterrupt:
        LOGGER.info("Worker stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
