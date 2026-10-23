# Development friction log

Record issues as they occur, including their impact, resolution, and remaining
work. Update existing entries when resolved. Never include credentials, tokens,
or sign-in codes.

## 2026-10-23 — Initial setup and milestone 1

| Issue | Impact | Resolution / next action | Status |
| --- | --- | --- | --- |
| AGENTS.md refers to `MVP_PLAN.md`, but the plan is at `docs/MVP_Plan.md`. | The documented source-of-truth path could not be followed literally. | Read the existing plan; correct the reference in AGENTS.md. | Resolved |
| No Git repository existed. | Milestone changes could not be committed. | Initialized `main`; committed the worker implementation as `e019adc`. | Resolved |
| boto3 was not installed. | The worker could not run against AWS. | Installed boto3 through uv during the migration in `7b522f4`. | Resolved |
| `python -m venv` failed during ensurepip because Windows sandbox temporary files were not writable. | pip setup could not finish. The elevated retry was declined. | Switched to the user's preferred uv workflow; `uv sync` installed dependencies successfully. | Superseded by uv |
| AWS Core documentation searches repeatedly returned an authentication request, even after reporting it accepted. | Could not retrieve AWS documentation through the plugin. | Used official AWS SDK documentation through web search. Plugin access has not been reverified. | Workaround available |
| Default AWS credentials were absent; `agent-triage-dev` had an expired login session. | Live SQS validation could not start. | No resources created. The user has since retired this identity; do not renew or use it. | Superseded by identity change |
| Git could not create `.git/index.lock` inside the sandbox. | Staging and commits failed. | Approved elevated Git operations succeeded. The same permission boundary may recur. | Workaround available |
| uv could not write interpreter cache files inside the sandbox. | Initial `uv sync` failed. | Approved elevated uv operations installed dependencies; all six tests and CLI help passed. | Workaround available |
| Local examples referenced the retired `agent-triage-dev` profile. | Running the examples would target the wrong identity. | Updated examples to use the intended `arjun` profile, explicitly marked as requiring configuration. | Resolved |
| New IAM user `arjun` existed without a local profile. | Could not verify identity or run milestone 1 against SQS. | Browser login succeeded after user reported adding `SignInLocalDevelopmentAccess`; caller identity verified as `arjun`. Live SQS test passed. | Resolved |
| Caller-identity request could not reach the AWS STS endpoint inside the sandbox. | Could not verify the new login locally. | Approved network access outside the sandbox succeeded. | Workaround available |
| boto3 could not use browser-login credentials without its CRT dependency. | First queue creation attempt failed before creating a queue. | Used `uv add "boto3[crt]>=1.42,<2"`; uv installed `awscrt`, and queue creation succeeded. | Resolved |
| A single worker receive cycle returned fewer orders than requested. | First two cycles processed two orders each, leaving one. | Expected SQS behavior; a third cycle processed the last order. No code change needed. | Resolved |

## Sign-in investigation history

### AWS sign-in retry

- User reported "invalid request" in the first browser sign-in attempt for `arjun`.
  The cause is not yet known.
- Started a fresh `aws login --profile arjun --region us-east-1 --remote` request.
  This flow asks for a browser authorization code in the local CLI.
- Attempting to cancel that flow and start a fresh automatic browser request
  was rejected by the tool before the replacement request ran.
- Status: unresolved; no successful sign-in or AWS resource creation confirmed.
- With user approval, started another automatic browser sign-in request for
  `arjun` in `us-east-1`; waiting for browser completion.
- User raised missing authorization permissions as a possible cause. Official
  AWS documentation identifies `SignInLocalDevelopmentAccess` (or equivalent
  permissions) as the requirement for this login flow. The user's assigned
  policies have not been inspected; the cause remains unconfirmed.
- Reference: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html
- User reports attaching `SignInLocalDevelopmentAccess` to `arjun`. A subsequent
  caller-identity check still found no local `arjun` profile; the browser flow
  had not completed. Started a fresh sign-in after the permission change.
- Final result: fresh automatic sign-in succeeded, and caller identity confirmed
  IAM user `arjun`. This resolves the sign-in blocker; it does not independently
  prove the original "invalid request" was caused by permissions.

## 2026-10-23 — Milestone 2: Broken mode

| Issue / observation | Impact | Resolution / next action | Status |
| --- | --- | --- | --- |
| Intentional processing failures return exit code 1 from `worker --once`. | A successful broken-mode demo appears as a failed shell command. | Expected: verified `Database connection failed` logs and confirmed messages remain queued. Documented the exit code. | Expected behavior |
| Received failed messages temporarily become in-flight. | Available count alone can briefly understate the backlog. | Checked available, in-flight, and delayed counts after visibility timeout; all five orders remained available. | Verified |

No additional development blockers were encountered. No dependencies or AWS
resources were added for this milestone. The simulated failure does not contact
a database. Two seed batches reuse sample order IDs; the five SQS messages are
separate orders for this demonstration.

## Milestone 3 — Container deployment in progress

- User approved ECR as the image registry; AGENTS.md now records that supporting
  service. Added a Dockerfile and restricted build context; no image built yet.
- Docker CLI is installed, but the Linux engine is unavailable. CLI startup
  stalled; direct Desktop launch exposed the user's reported error:
  `initializing Inference manager ... dockerInference ... The file cannot be accessed by the system`.
- The runtime socket exists as a Windows reparse point. Matching reports exist
  in Docker's issue tracker; the cause on this host is not yet confirmed.
- Investigating a repair that preserves Docker images and volumes. No ECS, ECR,
  IAM, security-group, or log-group resources have been created for milestone 3.
- AWS identity remains `arjun`. The existing default VPC and public subnet routes
  were inspected; no network configuration was changed.
- Docker failure matched a stale Windows AF_UNIX runtime socket. Stopped
  Docker/WSL, moved only `AppData/Local/Docker/run` to the recoverable backup
  `run.stale-20261023-030716`, and restarted Desktop. Engine verification passed.
- Local image build and CLI smoke test passed. Image runs as non-root user 10001.
- Initial deployment script attempt exposed empty-result handling bugs before
  creating resources; fixed and verified no resources had been created.
- Docker's Desktop credential helper returned `The stub received bad data` for
  ECR login. The deployment now uses a temporary isolated config with a
  short-lived ECR token and deletes it after the push.
- ECR image upload succeeded. Deployment then stopped on `iam:CreateRole` access
  denial for IAM user `arjun`. A scoped policy is provided at
  `infra/deployer-iam-policy.json`; it must be attached by an administrator.
- After the user attached the scoped policy, both ECS IAM roles were created.
  Deployment then exposed a strict-mode null handling bug when no existing
  security group matched. The script now handles that empty result before
  creating the group.
- Security-group creation was denied because the optional creation tag requires
  `ec2:CreateTags`, which `arjun` does not have. Removed only the optional tag;
  no broader permission is needed for the MVP.
- The `arjun` user cannot read Free Tier plan/usage or AWS Budgets. Cost status
  could not be confirmed from the CLI. Keep the worker at one minimum-size task
  only during verification, then scale it to zero.
- No ECS service or running Fargate task has been confirmed. Milestone 3 remains
  incomplete until healthy and broken deployments are both verified.

### Milestone 3 final verification

- The IAM policy attachment succeeded. Created the execution and task roles,
  ECS cluster/service, task definitions, outbound-only security group, and
  seven-day CloudWatch log group.
- Healthy task revision 1 ran one Fargate task, drained all five queued orders,
  and wrote five successful processing records to CloudWatch.
- Broken task revision 2 ran one Fargate task, wrote five simulated database
  errors, and did not delete the five new orders.
- SQS approximate counts briefly returned zero immediately after receipt, then
  showed the messages as in-flight. After the 30-second visibility timeout, all
  five appeared as available. This was expected eventual consistency.
- Scaled the ECS service to desired count zero after verification. Final task
  counts are desired 0, running 0, pending 0; no Fargate task or task public IP
  remains active.
- Final cost inventory reported 169,667,819 bytes across three ECR image
  digests, zero CloudWatch stored bytes at query time, and seven-day log
  retention. ECR/log/SQS storage and requests may still consume credits even
  with compute stopped; exact account charges remain unavailable to `arjun`.

## Checkpoint after milestone 3

- Dependency management: uv with committed `pyproject.toml` and `uv.lock`.
- Offline verification: nine tests pass, including failed processing without
  deletion, nonzero one-cycle exit status, and recovery after disabling broken mode.
- Identity verified: local profile `arjun` uses IAM user `arjun` in the configured AWS account.
- AWS resource created: SQS queue `cloudforge-orders-queue` in `us-east-1`.
- Milestone 1 live validation: seeded orders 1001 through 1005; all five were logged as
  processed across three receive cycles. Final available, in-flight, and delayed
  counts were all zero. The queue remains available; no worker is left running.
- Milestone 2 live validation: began with an empty queue; seeded three messages,
  ran broken mode, verified three remained, seeded two more, and ran broken mode
  again. Logs showed `Database connection failed`. Final counts: five available,
  zero in-flight, zero delayed. No successful processing/deletion in these runs.
- Current AWS state: five sample messages intentionally remain available in the
  queue. ECS service `orders-worker` retains broken-mode task definition revision
  2 but is scaled to zero. CloudWatch contains the corresponding error evidence.
- Milestones 1, 2, and 3 complete. Stop here; milestone 4 (AWS diagnostic
  functions) has not started.

## Milestone 4 — AWS diagnostic functions in progress

- AWS Core documentation search repeated its authorization request after the
  plugin reported that authorization was accepted. Used the installed boto3
  service models and live AWS responses as the documentation fallback.
- All three read-only functions passed live validation. ECS reported desired 0,
  running 0, pending 0, and unhealthy; SQS reported five available messages;
  CloudWatch returned ten matching error events.
- The ten log events represent two failed deliveries of each of five messages.
  This is expected because broken mode does not acknowledge messages and SQS
  makes them visible again after 30 seconds.
- No AWS resource was created, updated, or restarted for this milestone.

Milestone 4 is complete. Stop here; milestone 5 (MCP server) has not started.

## Checkpoint after milestone 4

- Fifteen offline tests pass: nine worker tests and six diagnostic tests.
- Live diagnostic results: ECS desired/running/pending 0/0/0 and unhealthy;
  SQS available/in-flight/delayed 5/0/0; CloudWatch failure search successful.
- The ECS service remains scaled to zero. Milestones 1 through 4 are complete.

## Milestone 5 — MCP server in progress

- Verified the current official Python SDK release is `mcp==2.3.0`. It supports
  the current protocol and clients using protocol version `2025-11-25`.
- Added the SDK with uv. The server binds to localhost and exposes only the
  three approved read-only tools over Streamable HTTP at `/mcp`.
- Kept the MCP SDK in the `mcp-server` optional dependency group so future
  orders-worker container builds do not install server-only packages.
- Rebuilt the local worker image and verified boto3 is installed while `mcp` is
  absent. No image was pushed to ECR.
- The first HTTP smoke client ran inside the desktop sandbox and could not reach
  the localhost server. Repeating the same client outside that boundary worked;
  the server received five successful HTTP requests.
- The official HTTP client listed exactly three tools and invoked all three.
  Every call returned structured content with `is_error=false`.
- Stopped the local MCP server after validation. ECS remained scaled to zero,
  and no AWS resource was changed.

Milestone 5 is complete. Stop here; milestone 6 (Strands + Bedrock agent) has not
started.

## Current checkpoint

- Seventeen offline tests pass, including MCP discovery, calls to all three
  tools, structured outputs, and input-bound validation.
- Live Streamable HTTP validation passed at `http://127.0.0.1:8000/mcp`; the
  temporary local server is stopped.
- ECS remains at desired/running/pending 0/0/0. Milestones 1 through 5 are
  complete.

## Milestone 6 — Strands + Bedrock agent in progress

- AWS Core documentation search repeatedly requested authorization after the
  plugin reported authorization was accepted. Used the official AWS and Strands
  documentation sites as the fallback.
- `strands-agents` 1.62 requires MCP below 2.2, while the CloudForge server uses
  MCP 2.3 for the required protocol support. UV initially rejected the combined
  dependency set. Declared the `agent` and `mcp-server` extras incompatible and
  documented `uv run --isolated` for the two processes. This preserves the
  current server and uses Strands' supported client version.
- Added one Strands agent using Nova Micro, an MCP tool allow-list, and explicit
  limits of 600 output tokens per model turn, five turns, and 2,400 output
  tokens per investigation.
- Four agent wiring tests and all 17 existing worker, diagnostics, and MCP tests
  pass in their respective locked UV environments.
- The read-only model discovery check failed because IAM user `arjun` does not
  have `bedrock:ListFoundationModels`. No Bedrock model was invoked and no
  inference charge was created. The narrow required policy is ready at
  `infra/bedrock-agent-iam-policy.json`; live validation is waiting for it to be
  attached.
- After the policy was attached, model discovery succeeded. The first agent
  launch stopped before inference because Strands rejects a `BedrockModel` that
  receives both a configured boto3 session and a separate `region_name`.
  Removed the redundant argument; the failed launch made no model call.
- The live Bedrock catalog included Nova Micro, Nova Lite, Nova 2 Lite, Claude
  Haiku 4.5, and many larger models. Kept Nova Micro because the task is a
  short, text-only investigation with exact tool names; the CLI retains a
  `--model-id` option if evaluation later justifies an upgrade.
- Live validation succeeded in two model turns. Nova Micro called
  `get_service_health`, `get_queue_status`, and `search_logs`; it correlated
  zero running workers, five queued orders, and repeated database failures into
  a coherent diagnosis and recommended remediation without taking action.
- Stopped the local MCP server after validation. The ECS service remains scaled
  to zero, and the single successful bounded investigation was the only Bedrock
  inference run.

Milestone 6 is complete. Stop here; milestone 7 (minimal React UI) has not
started.

## Checkpoint after milestone 6

- Twenty-one offline tests pass across the two isolated UV environments.
- Live Strands + Bedrock + MCP validation passed with all three approved tools.
- The local MCP server is stopped. ECS remains at desired/running/pending
  0/0/0, and the five demo messages remain available for the UI milestone.

## Milestone 7 — Minimal React UI

- Added a thin FastAPI endpoint around the existing incident agent and a single
  React + TypeScript screen. The UI derives completion checks from actual
  Strands tool metrics instead of displaying assumed progress.
- Kept the browser boundary narrow: the browser sends only the question and
  receives the diagnosis, tool names, model turns, token usage, and stop reason.
  AWS credentials and AWS SDK clients remain server-side.
- The first TypeScript build failed because TypeScript 7 required Vite's CSS
  side-effect import declaration. Added the standard `vite/client` type
  reference; the production build then passed.
- Visual QA in the local browser passed at the narrow app viewport. The landing,
  loading, completed checks, long diagnosis, metadata, and footer rendered
  without horizontal overflow.
- One live end-to-end submission completed in two model turns and 6,696 total
  tokens. The UI showed all three MCP checks and the expected diagnosis.
- Stopped both local servers after validation. ECS remained scaled to zero and
  no AWS resource was changed.

Milestone 7 is complete. Stop here; milestone 8 (submission materials) has not
started.

## Milestone 7 UI refinement

- The initial UI used generic gradients, glass panels, and marketing copy that
  did not match the developer-focused Strands product. Reworked the same MVP
  flow around the official Strands documentation visual language: a black
  canvas, monospaced typography, green and teal accents, documentation rails,
  thin rules, and command-style investigation output.
- Starting the local preview inside the desktop sandbox prevented uv from
  updating its interpreter cache. Running the same local-only server with the
  existing uv cache permission resolved the issue; no package was installed
  and no AWS service was called.
- The production TypeScript build and visual checks of the question, evidence,
  and diagnosis sections passed. The application behavior and API contract are
  unchanged.
- The first refinement copied too much of the Strands documentation layout and
  palette when only its font treatment was intended. Replaced the green and
  teal identity with CloudForge yellow and white, removed the right-hand
  on-page navigation, then removed the remaining left documentation rail. The
  final screen keeps the monospaced font influence in a focused, centered
  incident workspace without copying the Strands documentation structure.

The milestone 7 UI refinement is complete. Milestone 8 has not started.

## Milestone 8 — Demo preparation in progress

- The existing demo draft used an invented queue count and overstated how freely
  the agent selects its workflow. Replaced it with a preflight checklist and a
  two-to-three-minute script that uses live AWS values and accurately describes
  the prompt-bounded Strands investigation.
- Standardized the recorded flow on one Bedrock submission: `Why are orders
  delayed?` Alternative wording is reserved for a retake because the MVP has no
  conversation history and each submission consumes tokens.
- Added failure recovery and cost-safe teardown steps, including a final
  read-only check that ECS desired, running, and pending task counts are zero.

Demo script preparation is complete. The remaining milestone 8 submission
materials have not started.

- Added visible Alexa+ MCP positioning to the CloudForge header and opening UI
  copy so the demo immediately communicates the original hackathon use case.
  Kept Strands Agents and Amazon Bedrock credited separately as the underlying
  implementation stack.
- A second local preview could not bind to port 8001 because a FastAPI process
  was already serving the project. Reused that running local server to verify
  the rebuilt UI instead of interrupting it; no investigation was submitted.
