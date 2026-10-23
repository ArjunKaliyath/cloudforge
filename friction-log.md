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

## Current checkpoint

- Dependency management: uv with committed `pyproject.toml` and `uv.lock`.
- Offline verification: six tests and CLI help passed before the live test.
- Identity verified: local profile `arjun` uses IAM user `arjun` in the configured AWS account.
- AWS resource created: SQS queue `cloudforge-orders-queue` in `us-east-1`.
- Live validation: seeded orders 1001 through 1005; all five were logged as
  processed across three receive cycles. Final available, in-flight, and delayed
  counts were all zero. The queue remains available; no worker is left running.
- Milestone 1 complete. Stop here; milestone 2 (broken mode) has not started.
