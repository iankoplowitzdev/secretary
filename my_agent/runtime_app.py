"""AgentCore Runtime entrypoint for the secretary agent (US-7).

Wraps the same agent used for local CLI testing (see agent.py) with the
official bedrock_agentcore runtime contract (HTTP protocol: GET /ping health
check, POST /invocations, port 8080 — handled internally by
BedrockAgentCoreApp), so the identical persona, grounding rules, retrieval
tool, and guardrail apply whether invoked locally or via AgentCore.
"""

from bedrock_agentcore import BedrockAgentCoreApp

from my_agent.agent import build_agent

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(request: dict):
    """Handle one AgentCore invocation. Payload: {"message": "<user text>"}."""
    message = request.get("message") or request.get("prompt", "")
    agent = build_agent()
    async for event in agent.stream_async(message):
        yield event


if __name__ == "__main__":
    app.run()
