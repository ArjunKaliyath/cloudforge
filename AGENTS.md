# AGENTS.md

## Project

CloudForge is an Alexa+ hackathon MVP that demonstrates an agentic AWS incident investigation workflow.

Stack:

- Python
- FastAPI
- Strands Agents SDK
- Amazon Bedrock
- MCP over Streamable HTTP
- AWS ECS/Fargate
- AWS SQS
- AWS CloudWatch
- React + TypeScript

## Source of Truth

Before implementing anything, read:

`docs/MVP_Plan.md`

Build only the current MVP scope.

Do not add features outside the MVP unless explicitly requested.

## MVP Scope Lock

Allowed AWS services:

- ECS/Fargate
- SQS
- CloudWatch
- Bedrock

Allowed MCP tools:

- `get_service_health`
- `get_queue_status`
- `search_logs`

Optional only after the core flow works:

- `get_recent_deployments`

Do not add:

- RDS
- Lambda
- DLQ
- ALB
- API Gateway
- Terraform
- Secrets Manager
- AgentCore
- authentication
- persistent incident state
- automatic remediation
- multiple agents
- multiple failure scenarios

## Architecture

Use this dependency direction:

```text
React UI
   ↓
FastAPI Agent Backend
   ↓
Strands Agent + Bedrock
   ↓
MCP Client
   ↓
CloudForge MCP Server
   ↓
AWS Operations
   ↓
ECS / SQS / CloudWatch
```

Do not give the Strands agent direct boto3 access.

AWS access must happen through MCP tools.

## Development Rules

- Build the smallest working solution.
- Do not over-engineer.
- Prefer one file over multiple abstractions when the abstraction adds no immediate value.
- Use type hints for Python.
- Keep credentials out of source code.
- Use environment variables or the current AWS credential/session mechanism.
- Do not generate Terraform.
- Do not introduce unnecessary libraries.
- Use AWS Core documentation for current AWS APIs.
- Use the Strands documentation MCP server for current Strands APIs.
- Avoid general web search for AWS/Strands docs unless those sources are unavailable.

## Working Style

Maintain `friction-log.md` as development proceeds. Record issues, their impact,
resolution or next action, and status; update resolved entries. Never include
credentials, tokens, or sign-in codes.

For each task:

1. inspect existing code
2. identify the smallest required change
3. implement only that change
4. run it or test it
5. fix errors
6. summarize what changed
7. stop

Do not implement later milestones automatically.

## Git

Commit after each working milestone.

Examples:

```text
feat: add sqs orders queue worker
feat: deploy orders worker to ecs
feat: add aws diagnostic operations
feat: expose diagnostics through mcp
feat: add strands incident agent
feat: add minimal cloudforge ui
```

## Primary Demo Requirement

The MVP must reliably demonstrate:

```text
broken ECS worker
→ SQS backlog
→ CloudWatch errors
→ user asks why orders are delayed
→ agent checks multiple AWS services through MCP
→ agent identifies likely root cause
```

Optimize everything around making that flow work reliably.
