# CLAUDE.md

Guidance for Claude Code (and future contributors) working in this repo.

## Project overview

A public-facing AI "secretary" chatbot: a React frontend, backed by a
Strands agent deployed on Amazon Bedrock AgentCore Runtime, that answers
prospective employers' questions about the owner's work history, skills,
and projects — grounded in a Bedrock Knowledge Base built from a resume,
an about-me doc, and STAR-method answers. Guardrails keep it on-topic and
jailbreak-resistant.

The full build plan (numbered user stories, dependencies, and each story's
automated "stop checkpoint") lives in `docs/proj_spec.md` — read it before
starting new work to see what's done and what's next.

## Repo structure

| Path | What it is |
|---|---|
| `frontend/` | Vite + React + TypeScript chat UI. Own `package.json`/`node_modules`. |
| `my_agent/` | The Strands agent. `agent.py` (persona + CLI entrypoint), `runtime_app.py` (AgentCore container entrypoint), `tools/` (e.g. `kb_retrieve.py`). Uses the root `.venv`. |
| `infra/` | CDK (Python) app. One stack per file in `infra/infra/`: `knowledge_base_stack.py`, `guardrail_stack.py`, `runtime_stack.py`. Uses its own `infra/.venv`, separate from the root one. |
| `docs/kb-source/` | Real source documents (resume, about-me, STAR stories) that get ingested into the Knowledge Base. See its own `README.md` for update ownership. |
| `scripts/reingest_kb.sh` | Syncs `docs/kb-source/` to S3 and runs a Bedrock ingestion job — KB content changes are **not** picked up automatically. |
| `Dockerfile` | ARM64 container for AgentCore Runtime (ARM64 is required — x86 images will not start). |
| `Makefile` | Single source of truth for local-dev and deploy commands — see below. |
| `.claude/skills/` | `run-locally` and `deploy-to-aws` — detailed runbooks, including hard-won gotchas. Consult these before touching infra or the agent. |

## Common commands

Full list: `make help`. The frequently-used ones:

```
make frontend-dev              # chat UI dev server against a mock stream
make frontend-test             # Vitest
make agent-run MESSAGE="..."   # run the Strands agent locally (real AWS calls)
make docker-build               # build the AgentCore container (ARM64)
make docker-run                # run it locally on :8081
make synth-all                 # cdk synth every stack (cheap, no AWS calls)
make deploy-all                # cdk deploy all stacks, in dependency order
make invoke-runtime MESSAGE="..." # invoke the real deployed AgentCore Runtime
make reingest                   # re-sync docs/kb-source/ into the live KB
```

Two things worth knowing before using these:
- MESSAGE-taking targets build JSON payloads through a small Python helper
  rather than hand-rolled shell quoting. Don't bypass this with raw
  `aws`/`curl` calls unless you handle apostrophes/quotes carefully — a
  hand-rolled escape corrupted a payload's encoding once already.
- A green `cdk deploy` does not prove the deployed agent actually works —
  an IAM action name was subtly wrong once, deployed cleanly, and only a
  real `make invoke-runtime` call surfaced the failure. Always verify a
  runtime change with a live invocation, not just a successful deploy.

For anything deploy-related — stack dependency order, known CDK/Bedrock
gotchas, teardown — read `.claude/skills/deploy-to-aws/SKILL.md` first;
don't rediscover bugs that are already documented there.

## AWS account

Account `107674771027`, region `us-east-1` (both are `Makefile` defaults).
Credentials are SSO/login-based — if a command fails with a login/refresh
error, tell the user to run `aws login` themselves; don't retry blindly.

## Git workflow

One branch per unit of work (named after the user story, e.g.
`us-7-agentcore-runtime`), following this cycle:

1. Branch off `main`.
2. Do the work, verify it (the story's stop checkpoint in `docs/proj_spec.md`
   if applicable, or the relevant `make`/test target otherwise).
3. Commit with a message ending in `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
4. Merge to `main` with `--no-ff`, push, delete the branch.

Only commit and merge when explicitly asked to. Real infrastructure
deploys (`cdk deploy`, `docker push`, anything that costs money or creates
live AWS resources) should be run in the foreground with the user able to
see what's happening — don't delegate these silently to a background
subagent.

## Conventions

- Comments explain *why*, not *what* — e.g. note a non-obvious constraint
  or the reason a workaround exists, not a restatement of the code.
- Never hardcode Bedrock resource IDs (Knowledge Base ID, Guardrail
  ID/version, Runtime ARN) — they've already changed at least once each
  during development due to CDK replacements. Resolve them at runtime via
  CloudFormation stack outputs (see `kb_retrieve.py`'s
  `_resolve_knowledge_base_id()` for the pattern) or pass them explicitly
  as environment variables/CDK cross-stack references.
- Keep cost in mind: there's a $25/mo Bedrock spend budget alarm
  (`GuardrailStack`) — see `docs/proj_spec.md` for the reasoning behind
  cost choices already made (e.g. S3 Vectors over OpenSearch Serverless).
