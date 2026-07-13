"""Bedrock Knowledge Base retrieval tool for the secretary agent.

Queries the Bedrock Knowledge Base (deployed via the ``KnowledgeBaseStack``
CDK stack) for chunks relevant to a natural-language query, and returns them
as grounded context for the agent to synthesize an answer from.

The Knowledge Base ID is never hardcoded: it's resolved at runtime, either
from the ``KNOWLEDGE_BASE_ID`` environment variable or by looking up the
``KnowledgeBaseId`` CloudFormation output of the ``KnowledgeBaseStack`` stack
(the KB has been replaced at least once before, so its ID is not stable).
"""

import os
from functools import lru_cache

import boto3
from strands import tool

DEFAULT_STACK_NAME = "KnowledgeBaseStack"
DEFAULT_REGION = "us-east-1"


@lru_cache(maxsize=1)
def _resolve_knowledge_base_id() -> str:
    """Resolve the live Knowledge Base ID.

    Preference order:
    1. ``KNOWLEDGE_BASE_ID`` environment variable (explicit override).
    2. The ``KnowledgeBaseId`` output of the ``KnowledgeBaseStack``
       CloudFormation stack (or ``KB_STACK_NAME`` if set), in the region
       given by ``KB_REGION``/``AWS_REGION`` (default ``us-east-1``).
    """
    env_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if env_id:
        return env_id

    region = os.environ.get("KB_REGION") or os.environ.get("AWS_REGION") or DEFAULT_REGION
    stack_name = os.environ.get("KB_STACK_NAME", DEFAULT_STACK_NAME)

    cfn = boto3.client("cloudformation", region_name=region)
    response = cfn.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0].get("Outputs", [])
    for output in outputs:
        if output.get("OutputKey") == "KnowledgeBaseId":
            return output["OutputValue"]

    raise RuntimeError(
        f"Could not find a 'KnowledgeBaseId' output on CloudFormation stack "
        f"'{stack_name}' in region '{region}'. Set the KNOWLEDGE_BASE_ID "
        f"environment variable to override."
    )


def _get_agent_runtime_client():
    region = os.environ.get("KB_REGION") or os.environ.get("AWS_REGION") or DEFAULT_REGION
    return boto3.client("bedrock-agent-runtime", region_name=region)


@tool
def kb_retrieve(query: str, max_results: int = 5) -> str:
    """Retrieve grounded context about Ian Koplowitz from the Bedrock Knowledge Base.

    Use this tool for ANY question about Ian's work history, employers, job
    titles, skills, technologies, projects, interests, or behavioral/STAR
    stories. Always call this tool before answering such a question — never
    answer from memory or assumption. The Knowledge Base is built from Ian's
    real resume, an about-me narrative, and STAR-method behavioral stories.

    Args:
        query: A natural-language question or search phrase describing what
            you need to know (e.g. "Ian's most recent job title" or
            "STAR story about a difficult teammate").
        max_results: Maximum number of retrieved chunks to return (default 5).

    Returns:
        A formatted string of the most relevant retrieved chunks, each
        tagged with its source document. Returns a clear "no results" message
        if nothing relevant is found — this should be treated as grounds to
        say the information isn't available, not an invitation to guess.
    """
    knowledge_base_id = _resolve_knowledge_base_id()
    client = _get_agent_runtime_client()

    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": max_results}
        },
    )

    results = response.get("retrievalResults", [])
    if not results:
        return (
            "No relevant content was found in the Knowledge Base for this query. "
            "Do not fabricate an answer — tell the user this information isn't "
            "available."
        )

    formatted_chunks = []
    for i, result in enumerate(results, start=1):
        text = result.get("content", {}).get("text", "").strip()
        location = result.get("location", {}) or {}
        s3_location = location.get("s3Location", {}) or {}
        source_uri = s3_location.get("uri", "unknown source")
        score = result.get("score")
        score_str = f" (relevance: {score:.2f})" if isinstance(score, (int, float)) else ""
        formatted_chunks.append(
            f"[{i}] Source: {source_uri}{score_str}\n{text}"
        )

    return "\n\n".join(formatted_chunks)
