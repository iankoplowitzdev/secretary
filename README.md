# secretary

An AI "secretary" chatbot for my personal site: a React chat UI backed by an
agent running on Amazon Bedrock AgentCore Runtime, that answers a prospective
employer's or collaborator's questions about my work history, skills, and
projects — grounded in a Bedrock Knowledge Base built from my resume, an
about-me doc, and STAR-method behavioral stories, with a Bedrock Guardrail
keeping it on-topic and resistant to prompt injection.

## How it works

```
 Browser (React)
      │  POST /chat, streamed SSE
      ▼
 Lambda Function URL  ──  streams tokens back to the browser as they arrive,
 (Node.js, streaming)     signs the call to AgentCore with its own IAM role
      │                   so the browser never touches AWS credentials
      ▼
 Bedrock AgentCore Runtime
 (Strands agent, ARM64 container)
      │
      ├──▶ Bedrock Guardrail        blocks jailbreaks/prompt injection,
      │                             off-topic requests, and PII leakage
      │
      └──▶ Bedrock Knowledge Base   retrieves grounded context from my
           (S3 Vectors)             resume / about-me doc / STAR stories —
                                     the agent never answers from memory
```

The agent (built with [Strands](https://github.com/strands-agents/sdk-python))
is instructed to call a knowledge-base retrieval tool for any question about
my background and to answer only from what it retrieves, rather than
generating plausible-sounding facts about me.

## Tech stack

- **Frontend:** React + TypeScript + Vite
- **Agent:** [Strands Agents SDK](https://github.com/strands-agents/sdk-python) on Amazon Bedrock AgentCore Runtime (Amazon Nova Lite)
- **Grounding:** Bedrock Knowledge Base, S3 Vectors backend
- **Safety:** Bedrock Guardrails (content filters, denied topics, PII, prompt-attack detection)
- **Proxy:** Node.js Lambda with response streaming, exposed via a Function URL
- **Infrastructure:** AWS CDK (Python), one stack per AWS component

## Repo layout

| Path | What it is |
|---|---|
| `frontend/` | Vite + React + TypeScript chat UI |
| `my_agent/` | The Strands agent — persona, system prompt, and the Knowledge Base retrieval tool |
| `infra/` | CDK app: Knowledge Base, Guardrail, AgentCore Runtime, and Lambda proxy stacks |
| `lambda/proxy/` | The streaming Lambda proxy in front of AgentCore Runtime |
| `docs/` | Build plan (`proj_spec.md`) and Knowledge Base source documents |

## Running it locally

This project uses a `Makefile` as the entry point for both local dev and
deployment; see `make help` for the full list. A few highlights:

```
make frontend-dev              # chat UI dev server against a mock stream
make frontend-test             # frontend test suite
make agent-run MESSAGE="..."   # run the Strands agent locally
make docker-build && make docker-run   # run the AgentCore container locally
```

Running the agent or deploying infrastructure requires an AWS account with
Bedrock model/Knowledge Base/AgentCore access configured; see
`docs/proj_spec.md` for the full architecture and build plan, and
`.claude/skills/` for detailed runbooks.
