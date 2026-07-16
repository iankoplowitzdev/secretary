import os

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_iam as iam,
    aws_bedrockagentcore as agentcore,
)
from aws_cdk.aws_ecr_assets import DockerImageAsset, Platform
from constructs import Construct

RUNTIME_NAME = "secretary_agent_runtime"

# The Dockerfile and its build context (my_agent/) live at the repo root,
# one level up from infra/ — not relative to this CDK app's own cwd.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Must match my_agent/agent.py's MODEL_ID (kept as a separate constant here
# rather than importing agent.py, since infra/ and my_agent/ have separate
# venvs/dependency trees).
MODEL_ID = "amazon.nova-lite-v1:0"
MODEL_INFERENCE_PROFILE_ID = "us.amazon.nova-lite-v1:0"


class RuntimeStack(Stack):
    """Deploys the secretary agent container to Bedrock AgentCore Runtime (US-7)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        knowledge_base_id: str,
        knowledge_base_arn: str,
        guardrail_id: str,
        guardrail_arn: str,
        guardrail_version: str,
        memory: agentcore.Memory,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Build & push the container image (ARM64 — AgentCore requires
        # Graviton; x86 images will not start). CDK builds locally with
        # docker buildx and pushes to a CDK-managed ECR asset repo as part
        # of `cdk deploy`. ---
        image_asset = DockerImageAsset(
            self,
            "AgentImage",
            directory=REPO_ROOT,
            platform=Platform.LINUX_ARM64,
        )

        # --- Execution role: scoped to exactly what the agent needs at
        # runtime — invoke the model (+ guardrail), and query the Knowledge
        # Base. Nothing else. ---
        execution_role = iam.Role(
            self,
            "RuntimeExecutionRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*"
                    },
                },
            ),
        )
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    # Cross-region inference profiles can route to any region
                    # within their geo, so the underlying foundation-model
                    # permission must not be pinned to a single region.
                    f"arn:aws:bedrock:*::foundation-model/{MODEL_ID}",
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{MODEL_INFERENCE_PROFILE_ID}",
                ],
            )
        )
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:ApplyGuardrail"],
                resources=[guardrail_arn],
            )
        )
        execution_role.add_to_policy(
            iam.PolicyStatement(
                # IAM action namespace is "bedrock:", not
                # "bedrock-agent-runtime:", despite the boto3/CLI client
                # being called bedrock-agent-runtime — confirmed via a real
                # AccessDeniedException from a deployed invocation.
                actions=["bedrock:Retrieve"],
                resources=[knowledge_base_arn],
            )
        )
        # Short-term memory only (US-14): write new turns, read them back
        # within the same session, and delete/replace individual events. The
        # delete grant is not optional despite this agent never explicitly
        # deleting anything — confirmed via a real invocation that
        # AgentCoreMemorySessionManager internally deletes-and-recreates an
        # event when correcting/updating a message, and without
        # DeleteEvent that surfaces mid-stream as an AccessDeniedException,
        # not at deploy time. Using the construct's own grant methods rather
        # than hand-written PolicyStatements — this repo has already been
        # burned once by a subtly-wrong AgentCore IAM action name (see the
        # bedrock:Retrieve comment above), so let CDK's own grant helper own
        # the exact action list instead of guessing it again here.
        memory.grant_write(execution_role)
        memory.grant_read_short_term_memory(execution_role)
        memory.grant_delete_short_term_memory(execution_role)

        # AgentCore needs to pull the container image on cold start.
        image_asset.repository.grant_pull(execution_role)

        runtime = agentcore.Runtime(
            self,
            "Runtime",
            runtime_name=RUNTIME_NAME,
            agent_runtime_artifact=agentcore.AgentRuntimeArtifact.from_ecr_repository(
                image_asset.repository, tag=image_asset.image_tag
            ),
            execution_role=execution_role,
            environment_variables={
                # Passed explicitly rather than resolved via CloudFormation
                # DescribeStacks at runtime (as the CLI/local path does) —
                # avoids granting the execution role a CloudFormation
                # permission it doesn't otherwise need, and avoids an extra
                # API call on every cold start.
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
                "GUARDRAIL_ID": guardrail_id,
                "GUARDRAIL_VERSION": guardrail_version,
                "MEMORY_ID": memory.memory_id,
                "AWS_REGION": self.region,
            },
            # Defaults: HTTP protocol, IAM authorizer (SigV4), public network
            # — appropriate for this stage of the project. Revisit VPC mode
            # and a non-IAM authorizer before this is a production endpoint
            # the public frontend calls directly (US-8+).
        )

        # Exposed for cross-stack references within the same CDK app (e.g.
        # LambdaProxyStack, US-8).
        self.agent_runtime_arn = runtime.agent_runtime_arn

        CfnOutput(self, "RuntimeArnOutput", value=self.agent_runtime_arn)
        CfnOutput(self, "RuntimeIdOutput", value=runtime.agent_runtime_id)
