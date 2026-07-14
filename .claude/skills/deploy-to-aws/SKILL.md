---
name: deploy-to-aws
description: Deploy or update this project's AWS infrastructure via CDK -- the Knowledge Base, Guardrail, and AgentCore Runtime stacks. Use when asked to deploy, redeploy, update infrastructure, add/change a CDK stack, or troubleshoot a CDK deploy or AgentCore invocation failure for this project.
---

All commands below are `make` targets defined in the repo-root `Makefile`
(`make help` lists everything). Prefer these over hand-rolled `cdk`/`aws`
invocations -- they encode the account/region and fixes for real bugs hit
during development.

Account: `107674771027`, region: `us-east-1` (both hardcoded as `Makefile`
defaults; override via `AWS_ACCOUNT=... AWS_REGION=...` if this ever needs
to target somewhere else).

## Before deploying anything

1. Verify credentials: `aws sts get-caller-identity`. If it fails with a
   login/refresh error, tell the user to run `aws login` themselves
   (interactive) -- don't retry blindly.
2. First time only: `make infra-venv` (CDK's Python deps, separate from the
   root `.venv` used by the agent) and `make cdk-bootstrap` (already done
   for this account/region -- safe to re-run, it's idempotent).
3. Docker with buildx must be available for `deploy-runtime` (it builds and
   pushes an ARM64 image as part of `cdk deploy`): `docker buildx version`.

## The stacks, in dependency order

| Stack | `make` target | Contains |
|---|---|---|
| `KnowledgeBaseStack` | `make deploy-kb` | S3 source bucket, S3 Vectors bucket+index, Bedrock Knowledge Base, data source |
| `GuardrailStack` | `make deploy-guardrail` | Bedrock Guardrail (jailbreak/topic/PII policies), pinned version, $25/mo Bedrock spend budget alarm |
| `RuntimeStack` | `make deploy-runtime` | Docker image build+push, AgentCore Runtime, scoped execution role |

`RuntimeStack` depends on both others via direct CDK cross-stack references
(not CloudFormation exports) -- deploy `KnowledgeBaseStack` and
`GuardrailStack` first, or just run `make deploy-all` which does all three
in order.

`infra/infra/infra_stack.py` (`InfraStack`) is **unused dead scaffolding**
left over from initial project setup -- it's still registered in `app.py`
and synthesizes an empty stack, but nothing in this project depends on it.
Don't bother deploying it; consider removing it if it's still around when
cleaning up later.

## Standard flow

```
make synth-kb          # or synth-guardrail / synth-runtime / synth-all -- cheap, no AWS calls, catches schema errors before deploying
make deploy-kb          # or deploy-guardrail / deploy-runtime / deploy-all
```

After a `KnowledgeBaseStack` deploy where source docs changed:

```
make reingest           # syncs docs/kb-source/ to S3 and runs a Bedrock ingestion job -- KB changes are NOT picked up automatically
```

## Verifying a deploy actually worked

`cdk deploy` succeeding only proves CloudFormation accepted the resources --
it does **not** prove the deployed agent can actually do its job (a real bug
here: an IAM action name was subtly wrong, `cdk deploy` succeeded, and only
a live invocation surfaced the failure). After `deploy-runtime`, always
confirm with a real invocation, not just a green deploy:

```
make invoke-runtime MESSAGE="What are Ian's core skills?"
```

Look for `kb_retrieve` in the response with `success_count=1, error_count=0`
and real resume content in the answer -- not an apology about failing to
retrieve information.

## Known gotchas (hit for real during development -- don't rediscover these)

- **S3 Vectors metadata size limit**: Bedrock stores each chunk's text under
  the reserved `AMAZON_BEDROCK_TEXT` metadata key on the vector index. S3
  Vectors caps *filterable* metadata at 2KB/vector, which chunk text easily
  exceeds. Fix: mark it non-filterable via
  `metadata_configuration=CfnIndex.MetadataConfigurationProperty(non_filterable_metadata_keys=["AMAZON_BEDROCK_TEXT"])`.
  Without this, ingestion jobs fail with "Filterable metadata must have at
  most 2048 bytes."

- **Custom-named resources can't be replaced in place**: any CDK resource
  given an explicit fixed name (`index_name=`, `name=`, etc.) that later
  needs a property change requiring replacement will fail deploy with
  *"CloudFormation cannot update a stack when a custom-named resource
  requires replacing."* Fix: give it a new name (e.g. append `-v2`) so
  CloudFormation can create-then-delete instead of trying to reuse the name.

- **`CfnGuardrailVersion` is an immutable snapshot**: updating the
  Guardrail's `DRAFT` policy does **not** automatically produce a new
  version -- CloudFormation only cuts a new version when the
  `CfnGuardrailVersion` resource's *own* properties change. If you edit the
  guardrail's policy and redeploy without also bumping the
  `CfnGuardrailVersion`'s `description`, the deployed agent stays silently
  pinned to the stale pre-change version. Always bump that description
  (e.g. note what changed) alongside any policy edit.

- **Bedrock length limits on guardrail text fields**: both the Guardrail's
  top-level `description` and each denied topic's `definition` are capped
  at 200 characters -- exceeding either fails deploy with a clear validation
  error, but only at deploy time (not at `cdk synth`).

- **PII `ANONYMIZE` does not mean "let it through"**: it replaces matches
  with a placeholder (e.g. `{NAME}`) same as `BLOCK` in effect. There is no
  PII action that means "pass through unmasked" -- the only way to leave an
  entity type untouched is to omit it from `pii_entities_config` entirely.
  Setting `NAME` to `ANONYMIZE` once redacted "Ian" out of the model's own
  tool-planning text mid-turn and truncated the response before it ever
  called `kb_retrieve`.

- **IAM action namespace mismatch**: the Knowledge Base retrieve API is
  called via the `bedrock-agent-runtime` boto3/CLI client, but the actual
  IAM action is `bedrock:Retrieve`, not `bedrock-agent-runtime:Retrieve`
  (which doesn't exist and fails silently at synth/deploy time, only
  surfacing as `AccessDeniedException` on a real invocation).

- **Root `.venv` can go stale**: if it was created before the repo was
  renamed/moved, its `pip`/`python` shebang lines point at a path that no
  longer exists (`bad interpreter`). `rm -rf .venv && python3 -m venv .venv`
  fixes it -- `make agent-venv` does this automatically.

- **`botocore[crt]`**: this account's credential provider (SSO/login-based)
  requires it explicitly; plain `boto3`/`botocore` alone raises
  `MissingDependencyException` on the first Bedrock call. Already pinned in
  `my_agent/requirements.txt`.

- **`aws bedrock-agentcore invoke-agent-runtime` CLI quirks**: needs
  `--cli-binary-format raw-in-base64-out` to accept raw JSON text in
  `--payload` (otherwise it tries to parse your JSON as pre-encoded base64
  and fails with "Invalid base64"); `--runtime-session-id` must be at least
  33 characters; it takes a positional `<outfile>` argument (writes the
  response body to a file, doesn't print to stdout). `make invoke-runtime`
  handles all of this.

- **Local Docker testing can mask IAM bugs**: `docker-run` (see the
  run-locally skill) injects your own admin AWS credentials into the
  container, not the actual scoped execution role. A passing local Docker
  test proves the agent logic works; it proves nothing about whether the
  real execution role has the right permissions. Always confirm with
  `make invoke-runtime` against the deployed runtime.

- **`DockerImageAsset` build context path**: must be an absolute path (or
  relative to the CDK app's own cwd, which is `infra/`, not the repo root)
  -- `RuntimeStack` computes this via `os.path.abspath` from `__file__`
  rather than a bare relative string.

## Teardown

Destroy one stack at a time, in *reverse* dependency order (there's no
`destroy-all` on purpose):

```
make destroy-runtime      # first -- depends on the other two
make destroy-guardrail
make destroy-kb
```

Confirm with the user before running any `destroy-*` target -- these delete
real resources (the Knowledge Base's ingested content, the Guardrail, the
running agent endpoint).
