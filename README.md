# CloudForge

An Alexa+ hackathon MVP investigating a broken orders worker across ECS, SQS,
and CloudWatch using a Strands + Bedrock agent through bounded MCP tools.

The source of truth is [the MVP plan](docs/MVP_Plan.md). Development stops after
each milestone for review.

## Milestone 1: SQS and a local worker

Implemented: one Python CLI to create `cloudforge-orders-queue`, seed sample
orders, process them locally, and inspect approximate queue counts.
Live AWS validation is pending; the local login session needs renewal.

Prerequisites: Python 3.12+, AWS credentials with SQS access, and a configured
region. No credentials are stored in the repository. These PowerShell commands
use the existing `agent-triage-dev` profile in `us-east-1`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe orders.py --profile agent-triage-dev --region us-east-1 create
.venv\Scripts\python.exe orders.py --profile agent-triage-dev --region us-east-1 seed --count 5
.venv\Scripts\python.exe orders.py --profile agent-triage-dev --region us-east-1 status
.venv\Scripts\python.exe orders.py --profile agent-triage-dev --region us-east-1 worker
```

The worker logs each order ID and deletes the message after successful processing.
Stop it with Ctrl+C. Run `status` again to check the queue. Counts are approximate;
allow time for them to converge. For a bounded smoke run, use `worker --once`:
it long-polls once and handles up to ten messages. One empty receive does not
prove the queue is drained.

Queue creation is explicit; seeding and running the worker require an existing
queue. Required SQS actions are `CreateQueue`, `GetQueueUrl`, `SendMessage`,
`ReceiveMessage`, `DeleteMessage`, and `GetQueueAttributes` for the demo queue.

Messages contain JSON such as `{"order_id": "1001"}`. Invalid orders are logged
and left in the queue. Standard SQS delivery can repeat messages; this demo only
logs order IDs and has no external processing side effects.

## Validation

```powershell
python -m unittest discover -s tests -v
```

Tests use a standard-library fake SQS client and do not contact AWS. They cover
successful acknowledgement, failed processing, delete failures, seeding, and
empty receives. They can run before boto3 is installed.

Milestone 1 is complete only after real orders enter SQS, the worker processes
them, and queued/in-flight/delayed counts settle to zero. Broken mode,
container deployment, diagnostics, MCP, the agent, and UI are later milestones.
