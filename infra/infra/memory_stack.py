from aws_cdk import Stack, CfnOutput, aws_bedrockagentcore as agentcore
from constructs import Construct

MEMORY_NAME = "secretary_agent_memory"


class MemoryStack(Stack):
    """Bedrock AgentCore short-term memory for the secretary agent (US-14).

    Short-term memory only — no memory strategies configured, so no
    long-term/semantic extraction runs and no per-strategy namespace design is
    needed. This exists solely so the agent can recall prior turns within a
    single AgentCore session; cross-session recall is a separate, larger
    feature (namespaces, retrieval tuning, an actor-identity model that
    doesn't map cleanly onto anonymous public visitors) intentionally left for
    a future story.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        memory = agentcore.Memory(
            self,
            "Memory",
            memory_name=MEMORY_NAME,
            description="Short-term (within-session) conversation memory for the secretary agent.",
            # No memory_strategies passed — that's what keeps this long-term-
            # memory-free. Adding strategies later is additive, not breaking.
        )

        # Exposed for cross-stack references within the same CDK app (e.g.
        # RuntimeStack), mirroring KnowledgeBaseStack.knowledge_base_id and
        # GuardrailStack.guardrail_id.
        self.memory = memory
        self.memory_id = memory.memory_id
        self.memory_arn = memory.memory_arn

        CfnOutput(self, "MemoryIdOutput", value=self.memory_id)
        CfnOutput(self, "MemoryArnOutput", value=self.memory_arn)
