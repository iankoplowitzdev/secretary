---
name: run-locally
description: Run and test pieces of the secretary app locally -- the frontend chat UI dev server and tests, the Strands agent CLI, and the AgentCore-compatible Docker container. Use when asked to run, start, test, or debug the app locally, or to verify a local change before deploying.
---

All commands below are `make` targets defined in the repo-root `Makefile` --
run `make help` to list every target. Prefer these over hand-rolled
equivalents; they encode fixes for real bugs hit during development (see
Makefile comments), especially around safely passing messages containing
apostrophes/quotes into JSON payloads.

## Current state: what's runnable locally

Full end-to-end local dev is possible as of US-10: the frontend dev server
can talk to the real deployed Lambda proxy. Four independently runnable
pieces:

1. **Frontend** -- chat UI, against either the real deployed backend or a
   local mock streaming endpoint (see below for which one is active).
2. **Agent CLI** -- the Strands agent directly, via Python (real AWS calls:
   Bedrock model invoke, Knowledge Base retrieve, Guardrail).
3. **AgentCore container** -- the same agent, wrapped in the exact container
   that gets deployed to AgentCore Runtime, run via Docker (real AWS calls).
4. **Playwright E2E** -- loads the real frontend dev server in a real
   browser and sends an actual message; exercises whatever backend the dev
   server is configured for.

## 1. Frontend

```
make frontend-install   # first time only, or after package.json changes
make frontend-dev       # dev server with hot reload
make frontend-test      # Vitest unit tests, run once (not watch mode)
make frontend-e2e       # Playwright, real browser -- see below
make frontend-build     # production build (sanity check before deploying)
```

**Which backend the dev server uses** is controlled by
`frontend/.env.local` (gitignored -- copy `.env.example` to create it):

- `VITE_FUNCTION_URL` set to the deployed Function URL (see the
  deploy-to-aws skill for how to look it up) -> real backend, real grounded
  answers, real AWS calls.
- `VITE_FUNCTION_URL` unset -> falls back to an in-browser mock (canned
  responses, no network calls) -- useful for pure UI iteration with zero
  AWS dependency.

`frontend-e2e` runs against whichever of these is active. If it fails with
an empty response but no thrown error, check the browser console via a
one-off debug script with `page.on('console', ...)`/`page.on('requestfailed', ...)`
listeners before assuming the app logic is wrong -- a real CORS failure
here looked exactly like "the stream silently produced nothing" until the
browser console was actually inspected (see the deploy-to-aws skill's CORS
gotchas; curl/Node's `fetch` never catch these, only a real browser does).

## 2. Agent CLI

Requires the root `.venv` (separate from `infra/.venv`, which is CDK-only)
and valid AWS credentials -- run `aws sts get-caller-identity` first; if it
fails with a login/refresh error, tell the user to run `aws login`
themselves (interactive; you can't do this on their behalf) rather than
retrying blindly.

```
make agent-venv                              # first time, or if pip/python commands mysteriously break
make agent-run MESSAGE="Tell me about Ian's most recent role"
```

The agent resolves the live Knowledge Base ID and Guardrail ID/version at
runtime via CloudFormation stack outputs (`KnowledgeBaseStack`,
`GuardrailStack`) by default -- no need to pass them manually. Override with
`KNOWLEDGE_BASE_ID` / `GUARDRAIL_ID` / `GUARDRAIL_VERSION` env vars if
testing against something else.

**If `agent-venv` fails with `pip: bad interpreter`**: the venv was created
in a different directory (or the repo got renamed/moved) and its shebang
lines point at a path that no longer exists. `rm -rf .venv` and re-run
`make agent-venv` to rebuild it fresh -- this happened once already this
project.

## 3. AgentCore container (Docker)

This runs the *exact* container that gets deployed to AgentCore Runtime
(same Dockerfile, same `my_agent/runtime_app.py` entrypoint), so it's the
closest local approximation of production behavior.

```
make docker-build                                     # ARM64 build -- AgentCore requires Graviton, x86 images will not start
make docker-run                                       # starts on localhost:8081 (8080 was already taken on this machine)
make docker-ping                                      # health check
make docker-invoke MESSAGE="What are Ian's core skills?"
make docker-stop                                      # when done
```

**Important caveat**: `docker-run` injects *your own* AWS credentials (via
`aws configure export-credentials`) into the container, not the scoped IAM
execution role the real deployed runtime uses. A working local Docker test
does **not** prove the deployed runtime's IAM permissions are correct -- this
already caused a real bug to slip past local testing once (see the deploy
skill's gotcha list). Only a real `make invoke-runtime` call against the
deployed runtime (see the deploy-to-aws skill) actually proves the execution
role works.

If `docker-ping` fails immediately after `docker-run`, it's very likely just
a container-still-starting race -- wait a couple seconds and retry before
assuming something's broken.
