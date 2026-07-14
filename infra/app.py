#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.infra_stack import InfraStack
from infra.knowledge_base_stack import KnowledgeBaseStack
from infra.guardrail_stack import GuardrailStack
from infra.runtime_stack import RuntimeStack
from infra.lambda_proxy_stack import LambdaProxyStack


app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

knowledge_base_stack = KnowledgeBaseStack(app, "KnowledgeBaseStack", env=env)

guardrail_stack = GuardrailStack(app, "GuardrailStack", env=env)

runtime_stack = RuntimeStack(
    app,
    "RuntimeStack",
    env=env,
    knowledge_base_id=knowledge_base_stack.knowledge_base_id,
    knowledge_base_arn=knowledge_base_stack.knowledge_base_arn,
    guardrail_id=guardrail_stack.guardrail_id,
    guardrail_arn=guardrail_stack.guardrail_arn,
    guardrail_version=guardrail_stack.guardrail_version,
)

lambda_proxy_stack = LambdaProxyStack(
    app,
    "LambdaProxyStack",
    env=env,
    agent_runtime_arn=runtime_stack.agent_runtime_arn,
)

InfraStack(app, "InfraStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
