#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.knowledge_base_stack import KnowledgeBaseStack
from infra.guardrail_stack import GuardrailStack
from infra.memory_stack import MemoryStack
from infra.runtime_stack import RuntimeStack
from infra.lambda_proxy_stack import LambdaProxyStack


app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

knowledge_base_stack = KnowledgeBaseStack(app, "KnowledgeBaseStack", env=env)

guardrail_stack = GuardrailStack(app, "GuardrailStack", env=env)

memory_stack = MemoryStack(app, "MemoryStack", env=env)

runtime_stack = RuntimeStack(
    app,
    "RuntimeStack",
    env=env,
    knowledge_base_id=knowledge_base_stack.knowledge_base_id,
    knowledge_base_arn=knowledge_base_stack.knowledge_base_arn,
    guardrail_id=guardrail_stack.guardrail_id,
    guardrail_arn=guardrail_stack.guardrail_arn,
    guardrail_version=guardrail_stack.guardrail_version,
    memory=memory_stack.memory,
)

lambda_proxy_stack = LambdaProxyStack(
    app,
    "LambdaProxyStack",
    env=env,
    agent_runtime_arn=runtime_stack.agent_runtime_arn,
)

app.synth()
