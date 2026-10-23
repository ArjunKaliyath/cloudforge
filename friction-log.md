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
| New IAM user `arjun` exists, but no local `arjun` profile is configured. | Cannot yet verify identity or run milestone 1 against SQS. | User reports permissions assigned; these have not been verified. Sign in locally as `arjun`, verify caller identity, then create the queue, seed five orders, run the worker, and check counts settle to zero. | Open — blocks live validation |

## Current checkpoint

- Dependency management: uv with committed `pyproject.toml` and `uv.lock`.
- Offline verification: six tests and CLI help passed.
- Live AWS verification: pending; no CloudForge AWS resources created in this session.
- Intended IAM user: `arjun`. IAM user names and local CLI profile names are separate.
- Last profile inventory: `default`, `agent-triage-dev`; no `arjun` profile yet.
- Next milestone remains milestone 1; broken mode and later milestones have not started.
