import os

from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_lambda as lambda_,
    aws_lambda_nodejs as nodejs,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct

# lambda/proxy/ lives at the repo root, not relative to this CDK app's own
# cwd (infra/) -- same reasoning as RuntimeStack's REPO_ROOT.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class LambdaProxyStack(Stack):
    """Streaming Lambda proxy in front of AgentCore Runtime (US-8).

    Public, unauthenticated Function URL so the browser never needs AWS
    credentials. No WAF/CloudFront in front of it (deferred -- see
    docs/proj_spec.md's Phase 2 backlog for why); reserved concurrency and
    the Bedrock spend budget alarm (KnowledgeBaseStack) are the interim
    cost/abuse controls.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        agent_runtime_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = nodejs.NodejsFunction(
            self,
            "ProxyFunction",
            entry=os.path.join(REPO_ROOT, "lambda", "proxy", "index.mjs"),
            deps_lock_file_path=os.path.join(
                REPO_ROOT, "lambda", "proxy", "package-lock.json"
            ),
            handler="handler",
            # Response streaming (awslambda.streamifyResponse) is supported
            # on Node.js managed runtimes only -- confirmed against current
            # AWS docs before picking this runtime over Python.
            runtime=lambda_.Runtime.NODEJS_22_X,
            architecture=lambda_.Architecture.ARM_64,
            timeout=Duration.seconds(60),
            memory_size=256,
            # CDK defaults to 731 days (2 years) if left unset -- far more
            # than needed for a lightweight proxy's logs at this traffic
            # scale; not a real cost concern here but not worth keeping.
            log_retention=logs.RetentionDays.ONE_MONTH,
            environment={
                "AGENT_RUNTIME_ARN": agent_runtime_arn,
            },
            # No explicit reserved_concurrent_executions: this account's
            # total Lambda concurrency limit is only 10 (not AWS's standard
            # 1000 default), and AWS requires >=10 unreserved executions
            # account-wide at all times -- with a ceiling of exactly 10,
            # there's no room to carve out a reservation for any function
            # without violating that floor (confirmed via a real deploy
            # failure: "decreases account's UnreservedConcurrentExecution
            # below its minimum value of [10]"). The account's inherent
            # 10-concurrent-execution ceiling already caps this function's
            # worst-case parallel blast radius in practice (nothing else in
            # this account meaningfully competes for it), so this still
            # serves the same purpose reserved_concurrent_executions would
            # have. Revisit with an explicit reservation if/when the account
            # concurrency quota is raised.
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                # The actual authorization check is against the runtime's
                # ENDPOINT ARN (.../runtime-endpoint/DEFAULT), a sub-resource
                # of the bare runtime ARN -- confirmed via a real
                # AccessDeniedException naming that exact resource. The bare
                # ARN alone does not match it.
                resources=[agent_runtime_arn, f"{agent_runtime_arn}/*"],
            )
        )

        function_url = fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,
            cors=lambda_.FunctionUrlCorsOptions(
                # No fixed frontend domain yet (Amplify Hosting is US-11) --
                # tighten to the real origin once one exists.
                allowed_origins=["*"],
                allowed_methods=[lambda_.HttpMethod.POST],
                # A JSON POST body triggers a CORS preflight (application/json
                # isn't a "simple" content-type) -- without explicitly
                # allowing the Content-Type header, browsers block the real
                # request after the preflight is rejected. Curl and Node's
                # fetch don't enforce CORS at all, so this only breaks in an
                # actual browser -- confirmed via a real Playwright run
                # against a live dev server where the request silently
                # failed and the UI showed no response text.
                allowed_headers=["Content-Type"],
            ),
        )

        CfnOutput(self, "FunctionUrlOutput", value=function_url.url)
