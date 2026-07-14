# AgentCore Runtime requires ARM64 (Graviton) — x86 images will not start.
FROM --platform=linux/arm64 python:3.12.4-slim AS builder
WORKDIR /app
RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY my_agent/requirements.txt my_agent/requirements.txt
RUN pip install --no-cache-dir -r my_agent/requirements.txt
COPY my_agent my_agent

FROM --platform=linux/arm64 python:3.12.4-slim
RUN useradd -r -u 1001 appuser
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
EXPOSE 8080
# BedrockAgentCoreApp binds to 0.0.0.0 automatically when it detects it's
# running in a container (via /.dockerenv). AgentCore routes traffic to the
# container internally — this must never be exposed directly to the internet.
CMD ["python", "-m", "my_agent.runtime_app"]
