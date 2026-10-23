# CloudForge

An Alexa+ hackathon MVP investigating a broken orders worker across ECS, SQS,
and CloudWatch using a Strands + Bedrock agent through bounded MCP tools.

The source of truth is [the MVP plan](docs/MVP_Plan.md). Development stops after
each milestone for review.
Development issues and their status are tracked in [the friction log](friction-log.md).

## Milestone 1: SQS and a local worker

Implemented: one Python CLI to create `cloudforge-orders-queue`, seed sample
orders, process them locally, and inspect approximate queue counts.
Live AWS validation passed: five sample orders were sent to the real SQS queue,
processed by the local worker across three receive cycles, and deleted. Final
available, in-flight, and delayed message counts were all zero.

Prerequisites: uv, Python 3.12+, AWS credentials with SQS access, and a configured
region. No credentials are stored in the repository. These PowerShell commands
use the local `arjun` profile, verified as IAM user `arjun`, in `us-east-1`.
Creating an IAM user in AWS does not create a local CLI profile; this profile
was configured separately using `aws login`.

```powershell
uv sync --locked
uv run orders.py --profile arjun --region us-east-1 create
uv run orders.py --profile arjun --region us-east-1 seed --count 5
uv run orders.py --profile arjun --region us-east-1 status
uv run orders.py --profile arjun --region us-east-1 worker
```

uv manages `.venv` automatically; no activation or pip installation is needed.
Dependencies are declared in `pyproject.toml` and pinned in the committed
`uv.lock`. Use `uv add <package>` when adding a dependency, and commit both files.
The `boto3[crt]` dependency includes support for credentials from `aws login`.

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
uv run --locked --extra mcp-server python -m unittest discover -s tests -v
```

Tests use fake AWS clients and an in-memory MCP client; they do not contact AWS.
They cover worker behavior, diagnostic response mapping, typed MCP schemas,
structured tool results, and invalid MCP input. No real credentials are needed.

Milestone 1 is complete: real orders entered SQS, the worker processed
them, and queued/in-flight/delayed counts reached zero. Container deployment,
diagnostics, MCP, the agent, and UI are later milestones.

## Milestone 2: Broken mode

Set `BROKEN_MODE=true` to simulate a processing failure. No database is created
or contacted. Valid orders produce `Database connection failed` errors instead
of being processed or deleted. Without this setting, the worker behaves normally.

```powershell
$env:BROKEN_MODE = "true"
uv run orders.py --profile arjun --region us-east-1 seed --count 3
uv run orders.py --profile arjun --region us-east-1 worker --once
uv run orders.py --profile arjun --region us-east-1 status
```

`worker --once` returns exit code 1 when a received order fails; this is expected
in broken mode. The continuous worker keeps polling and logging failures.
Received orders are temporarily in-flight for the queue's 30-second visibility
timeout, then become available again. Add more orders while broken mode is
enabled to demonstrate a growing backlog. Queue counts are approximate.

To restore normal processing, set `$env:BROKEN_MODE = "false"` and run `worker`
again. Stop it with Ctrl+C once counts settle to zero. Logs currently appear in
the local terminal; CloudWatch logging is part of the ECS milestone.

Live validation passed: the backlog grew from zero to three, then five orders.
Broken worker runs logged processing errors and did not delete the received
orders. Final counts were five available, zero in-flight, and zero delayed.
All nine offline tests pass, including recovery after disabling broken mode.

## Milestone 3: ECS/Fargate deployment

The worker now runs as a Linux container on ECS/Fargate. Amazon ECR stores the
image, and the `awslogs` driver sends container output to
`/ecs/cloudforge/orders-worker` with seven-day retention. The task uses the
smallest Fargate size (0.25 vCPU and 0.5 GB), a read-only root filesystem, a
non-root container user, a queue-scoped task role, and an outbound-only security
group. It runs in the default VPC with a temporary public IP so it can reach SQS,
ECR, and CloudWatch without a NAT gateway.

Build the local image, then deploy healthy or broken mode:

```powershell
docker build -t cloudforge-orders-worker:local .
& .\infra\deploy-ecs.ps1 -Profile arjun -Region us-east-1 -BrokenMode:$false
& .\infra\deploy-ecs.ps1 -Profile arjun -Region us-east-1 -BrokenMode:$true
```

Each deployment creates a new task-definition revision and sets the service to
one running task. The script is safe to rerun against the named MVP resources.
`infra/deployer-iam-policy.json` contains the narrow IAM additions needed to
create and pass the two ECS roles; it is not an application runtime policy.

After a demo, stop runtime charges by scaling the service to zero:

```powershell
aws ecs update-service `
  --cluster cloudforge `
  --service orders-worker `
  --desired-count 0 `
  --profile arjun `
  --region us-east-1
```

At zero tasks, there is no running Fargate compute or task public IP. The ECS
configuration remains ready to restart. ECR image storage, retained CloudWatch
logs, SQS storage/requests, and future API use can still incur small charges or
consume credits. The `arjun` IAM user currently cannot read Free Tier usage or
AWS Budgets, so check those pages from an identity with billing access.

Live validation passed in both modes. Healthy mode drained five queued orders
and wrote `Processed order_id=...` records to CloudWatch. Broken mode wrote five
`Database connection failed` records and left all five orders in SQS. The final
cost-safe state is five available messages and an ECS service with desired,
running, and pending task counts all equal to zero.

## Milestone 4: AWS diagnostic functions

`diagnostics.py` provides the three read-only operations required by the MVP:

- `get_service_health(service_name)` reads desired, running, and pending ECS
  task counts. A service is healthy only when it is active, desires at least one
  task, all desired tasks are running, no task is pending, and deployment has
  not failed.
- `get_queue_status(queue_name)` reads approximate available, in-flight, and
  delayed SQS counts and returns their total.
- `search_logs(log_group, query)` searches for an exact text phrase. It defaults
  to the last 60 minutes and 20 results, with a hard maximum of 100 results.

Run each diagnostic independently with the local AWS profile:

```powershell
uv run --locked diagnostics.py --profile arjun --region us-east-1 service orders-worker
uv run --locked diagnostics.py --profile arjun --region us-east-1 queue cloudforge-orders-queue
uv run --locked diagnostics.py --profile arjun --region us-east-1 logs /ecs/cloudforge/orders-worker "Database connection failed" --lookback-minutes 180 --limit 10
```

Live validation found the expected incident evidence: ECS desired/running counts
were both zero, SQS had five available messages, and CloudWatch returned repeated
database-failure records. Standard SQS can redeliver an unacknowledged message
after its visibility timeout, so one failed order may produce multiple log events.
The functions use injectable boto3 clients for offline testing and are ready to
be wrapped as bounded MCP tools in milestone 5.

## Milestone 5: Streamable HTTP MCP server

`mcp_server.py` exposes exactly three read-only tools:

- `get_service_health`
- `get_queue_status`
- `search_logs`

The official MCP Python SDK derives typed input schemas from the tool function
parameters and structured output schemas from Pydantic result models. The server
binds to `127.0.0.1:8000` by default and serves Streamable HTTP at `/mcp`.

Install the MCP server dependency group and start the server with the local AWS
profile and region:

```powershell
uv sync --locked --extra mcp-server
$env:AWS_PROFILE = "arjun"
$env:AWS_DEFAULT_REGION = "us-east-1"
uv run --locked --extra mcp-server mcp_server.py
```

An MCP client connects to:

```text
http://127.0.0.1:8000/mcp
```

Override `CLOUDFORGE_MCP_HOST` or `CLOUDFORGE_MCP_PORT` when needed. Keep the
default localhost binding during development. The server has no arbitrary AWS
or shell tool and performs no write operation.

Live validation used the official MCP client over the HTTP endpoint. It listed
exactly the three approved tools, invoked each one, and received valid structured
results with no tool errors. The server was stopped afterward. The ECS worker
remained at zero tasks throughout the test.

## Milestone 6: Strands + Bedrock incident agent

`incident_agent.py` creates one Strands agent backed by Amazon Nova Micro in
Bedrock. Nova Micro is the low-cost text model used for this MVP. The agent can
discover only the three CloudForge tools through the MCP client. Its toolset has
no direct infrastructure client, shell, or remediation capability.

The model is limited to 600 output tokens per turn. Each investigation is also
limited to five model turns and 2,400 output tokens in total. Those limits
prevent an accidental tool loop from producing an unbounded model bill.

The local IAM user needs the narrow permissions in
`infra/bedrock-agent-iam-policy.json`. The policy permits read-only model
discovery plus non-streaming invocation of only Nova Micro in `us-east-1`.

Strands currently requires an older MCP client SDK than the MCP 2.3 server.
UV therefore locks them as incompatible extras. Run the server and agent in two
isolated environments so each process receives the correct SDK version.

In the first PowerShell terminal, start the MCP server:

```powershell
$env:AWS_PROFILE = "arjun"
$env:AWS_DEFAULT_REGION = "us-east-1"
uv run --isolated --locked --extra mcp-server mcp_server.py
```

In a second PowerShell terminal, run one investigation:

```powershell
uv run --isolated --locked --extra agent incident_agent.py `
  --profile arjun `
  --region us-east-1 `
  "Why are orders delayed?"
```

The command prints the diagnosis, the MCP tools that were actually used, the
number of model turns, token usage, and the stop reason.

Live validation passed with Nova Micro. In two model turns the agent called all
three tools, reported zero desired and running ECS tasks, found five available
SQS messages, and correlated repeated `Database connection failed` CloudWatch
records. It recommended investigating the connection and restarting worker
capacity without executing remediation. This simple, tightly prompted workflow
does not currently justify a more expensive model.
