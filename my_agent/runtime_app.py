"""AgentCore Runtime entrypoint for the secretary agent (US-7).

Wraps the same agent used for local CLI testing (see agent.py) with the
official bedrock_agentcore runtime contract (HTTP protocol: GET /ping health
check, POST /invocations, port 8080 — handled internally by
BedrockAgentCoreApp), so the identical persona, grounding rules, retrieval
tool, guardrail, and memory (US-14) apply whether invoked locally or via
AgentCore.
"""

import uuid

from bedrock_agentcore import BedrockAgentCoreApp

from my_agent.agent import build_agent

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(request: dict, context):
    """Handle one AgentCore invocation. Payload: {"message": "<user text>"}.

    ``context`` is populated by BedrockAgentCoreApp from the invocation's
    AgentCore session header (not from the request body) whenever the
    entrypoint declares a second parameter literally named ``context`` — this
    is how the Lambda proxy's ``runtimeSessionId`` actually reaches the agent.
    Falls back to a fresh random session (no recall) for local testing paths
    that don't go through a real AgentCore session, e.g. `docker-run`/`docker-invoke`.
    """
    message = request.get("message") or request.get("prompt", "")
    session_id = context.session_id or str(uuid.uuid4())
    agent = build_agent(session_id=session_id)
    async for event in agent.stream_async(message):
        yield event


if __name__ == "__main__":
    app.run()
