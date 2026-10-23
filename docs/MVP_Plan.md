# CloudForge MVP Plan

## Goal

Build a working Alexa+ hackathon submission where a Strands + Bedrock agent investigates a real AWS failure through a self-hosted MCP server.

The system must demonstrate autonomous investigation across:

- ECS
- SQS
- CloudWatch

## Demo Scenario

A simple orders worker processes messages from SQS.

Healthy:

```text
SQS
 ↓
ECS orders-worker
 ↓
messages processed successfully
```

Broken:

```text
ECS orders-worker fails
        ↓
messages stop processing
        ↓
SQS backlog grows
        ↓
CloudWatch receives errors
```

User asks:

> Why are orders delayed?

Agent should:

1. check ECS health
2. check SQS backlog
3. search CloudWatch logs
4. correlate the evidence
5. explain the likely root cause

## Architecture

```text
React UI
    ↓
FastAPI Agent Backend
    ↓
Strands Agent
    ↓
Amazon Bedrock
    ↓
MCP Client
    ↓
Streamable HTTP
    ↓
CloudForge MCP Server
    ↓
AWS
 ┌───────┬───────┬────────────┐
 │ ECS   │ SQS   │ CloudWatch │
 └───────┴───────┴────────────┘
```

## Milestone 1 — SQS + Local Worker

Create:

`cloudforge-orders-queue`

Write a Python worker that:

1. receives messages
2. logs the order ID
3. deletes successful messages

Provide a small script to seed test messages.

Example:

```json
{
  "order_id": "1001"
}
```

Success:

- messages enter SQS
- worker processes them
- queue returns to zero

## Milestone 2 — Broken Mode

Add:

```text
BROKEN_MODE=true
```

When enabled, processing should fail with a clear error such as:

```text
Database connection failed
```

Do not build a real database.

Success:

- messages remain/unprocessed
- queue backlog grows
- errors are visible

## Milestone 3 — ECS/Fargate

Containerize the worker.

Deploy it to ECS/Fargate.

Success:

- worker runs as an ECS task/service
- worker processes SQS messages
- logs appear in CloudWatch

Then deploy broken mode.

Success:

- worker failure is visible
- queue backlog grows
- CloudWatch contains errors

## Milestone 4 — AWS Diagnostic Functions

Implement Python functions for:

```text
get_service_health(service_name)
get_queue_status(queue_name)
search_logs(log_group, query)
```

Use boto3.

Example outputs:

```json
{
  "service": "orders-worker",
  "desired_tasks": 1,
  "running_tasks": 0,
  "healthy": false
}
```

```json
{
  "queue": "cloudforge-orders-queue",
  "messages_available": 120
}
```

Test these functions independently before MCP.

## Milestone 5 — MCP Server

Expose the three diagnostic functions as MCP tools.

Requirements:

- MCP spec 2025-11-25 or later
- Streamable HTTP
- typed inputs
- structured outputs

Tools:

```text
get_service_health
get_queue_status
search_logs
```

Do not expose arbitrary boto3 or shell access.

Success:

- an MCP client can invoke all three tools

## Milestone 6 — Strands + Bedrock Agent

Create one Strands agent using a Bedrock model.

The agent should have access to the MCP server.

System behavior:

```text
When investigating an AWS issue:

- gather evidence before concluding
- use multiple relevant tools
- never invent infrastructure state
- explain the evidence
- recommend remediation
- do not execute destructive actions
```

Test:

> Why are orders delayed?

Success:

- agent invokes multiple MCP tools
- agent identifies worker failure + queue backlog + CloudWatch errors
- agent produces a coherent diagnosis

## Milestone 7 — Minimal UI

Build one React screen.

Required:

```text
CloudForge

[ Why are orders delayed? ]

Investigating...

✓ Checked ECS
✓ Checked SQS
✓ Checked CloudWatch

Diagnosis:
...
```

No dashboards.

No authentication.

No settings.

## Milestone 8 — Submission

Finish:

- README
- architecture image or simple diagram
- Devpost description
- friction log if useful
- demo video

## Stretch Goal

Only after everything above works:

Add:

```text
get_recent_deployments
```

This lets the agent correlate:

```text
new deployment
→ worker failure
→ queue backlog
```

Do not build rollback execution unless the entire submission is already complete.

## Definition of Done

Submission-ready means:

- SQS queue works
- ECS worker works
- broken mode works
- SQS backlog becomes real
- CloudWatch errors are real
- MCP server works over Streamable HTTP
- three diagnostic tools work
- Strands uses Bedrock
- agent autonomously invokes multiple tools
- diagnosis works reliably
- React UI demonstrates it
- demo video is recorded
