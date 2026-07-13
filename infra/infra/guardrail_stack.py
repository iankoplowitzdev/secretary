from aws_cdk import (
    Stack,
    CfnOutput,
    aws_bedrock as bedrock,
)
from constructs import Construct

GUARDRAIL_NAME = "secretary-guardrail"

# Content filter strength for hate/insults/sexual/violence/misconduct.
# HIGH gives the strongest filtering; this is a small, low-traffic public
# chatbot so we favor over-blocking borderline content over under-blocking.
STANDARD_FILTER_STRENGTH = "HIGH"

DENIED_TOPICS = [
    {
        "name": "UnrelatedGeneralKnowledge",
        "definition": (
            "Requests for general knowledge, trivia, or assistance unrelated "
            "to Ian Koplowitz's background — e.g. unrelated factual "
            "questions, homework help, or general-purpose assistant tasks."
        ),
        "examples": [
            "What's the capital of France?",
            "Write me a Python script to scrape a website.",
            "What's a good recipe for banana bread?",
            "Can you help me with my calculus homework?",
        ],
    },
    {
        "name": "OtherIndividualsPersonalInfo",
        "definition": (
            "Requests for personal, private, or identifying information "
            "about people other than Ian Koplowitz — e.g. colleagues, "
            "references, or family — such as contact details or addresses."
        ),
        "examples": [
            "What is Ian's manager's phone number?",
            "Can you give me the home address of Ian's former coworker?",
            "Tell me something private about Ian's family.",
        ],
    },
    {
        "name": "FinancialOrLegalAdvice",
        "definition": (
            "Requests for financial, legal, medical, or investment advice, "
            "including compensation negotiation strategy or contract review, "
            "which is out of scope for a career-background Q&A assistant."
        ),
        "examples": [
            "What salary should I offer Ian?",
            "Can you review this employment contract for me?",
            "What stocks should I invest in?",
        ],
    },
]

# PII entity types plausibly present in the Knowledge Base (resume / about-me
# doc) that we want to pass through completely untouched, since the bot's
# whole job is discussing this person by name (e.g. "what's a good way to
# reach Ian?"). These are deliberately left OUT of pii_entities_config below
# rather than set to ANONYMIZE: ANONYMIZE still replaces matches with a
# placeholder (e.g. "{NAME}"), it does not mean "let it through" — using it
# here caused the guardrail to redact "Ian" out of the model's own
# tool-planning text mid-turn and truncate the response before it ever
# called kb_retrieve. Omitting an entity type from the policy entirely is
# the only way for it to pass through unmodified.
#
# Everything else gets BLOCK action via a broad denylist of common PII types
# unlikely to legitimately appear in a resume/about-me doc.
BLOCKED_PII_TYPES = [
    "PHONE",
    "ADDRESS",
    "AGE",
    "USERNAME",
    "PASSWORD",
    "DRIVER_ID",
    "LICENSE_PLATE",
    "VEHICLE_IDENTIFICATION_NUMBER",
    "CREDIT_DEBIT_CARD_CVV",
    "CREDIT_DEBIT_CARD_EXPIRY",
    "CREDIT_DEBIT_CARD_NUMBER",
    "PIN",
    "INTERNATIONAL_BANK_ACCOUNT_NUMBER",
    "SWIFT_CODE",
    "IP_ADDRESS",
    "MAC_ADDRESS",
    "AWS_ACCESS_KEY",
    "AWS_SECRET_KEY",
    "US_BANK_ACCOUNT_NUMBER",
    "US_BANK_ROUTING_NUMBER",
    "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER",
    "US_PASSPORT_NUMBER",
    "US_SOCIAL_SECURITY_NUMBER",
    "CA_HEALTH_NUMBER",
    "CA_SOCIAL_INSURANCE_NUMBER",
    "UK_NATIONAL_HEALTH_SERVICE_NUMBER",
    "UK_NATIONAL_INSURANCE_NUMBER",
    "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER",
]


class GuardrailStack(Stack):
    """CDK-defined Bedrock Guardrail for the secretary agent (US-6).

    Scope note: this stack ONLY provisions the guardrail resource itself.
    Wiring the resulting guardrail ID/version into the Strands agent's model
    config (my_agent/agent.py) is explicitly out of scope here — see
    CfnOutputs below for what the orchestrator needs to complete that wiring.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Content filters: hate/insults/sexual/violence/misconduct + the
        # native prompt-attack (prompt injection / jailbreak) filter. Applied
        # to both input and output at HIGH strength. ---
        content_filter_types = [
            "SEXUAL",
            "VIOLENCE",
            "HATE",
            "INSULTS",
            "MISCONDUCT",
            "PROMPT_ATTACK",
        ]
        content_filters = []
        for filter_type in content_filter_types:
            if filter_type == "PROMPT_ATTACK":
                # PROMPT_ATTACK only supports input-side detection (a prompt
                # attack lives in the user's/tool's input, not the model's
                # output) — output_strength is required by the CFN schema but
                # is a no-op for this type; output detection is disabled.
                content_filters.append(
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type=filter_type,
                        input_strength=STANDARD_FILTER_STRENGTH,
                        output_strength="NONE",
                        input_action="BLOCK",
                        input_enabled=True,
                        output_enabled=False,
                    )
                )
            else:
                content_filters.append(
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type=filter_type,
                        input_strength=STANDARD_FILTER_STRENGTH,
                        output_strength=STANDARD_FILTER_STRENGTH,
                        input_action="BLOCK",
                        output_action="BLOCK",
                        input_enabled=True,
                        output_enabled=True,
                    )
                )

        # --- Denied topics: keep the bot scoped to career/background Q&A. ---
        topics_config = [
            bedrock.CfnGuardrail.TopicConfigProperty(
                name=topic["name"],
                definition=topic["definition"],
                examples=topic["examples"],
                type="DENY",
                input_action="BLOCK",
                output_action="BLOCK",
                input_enabled=True,
                output_enabled=True,
            )
            for topic in DENIED_TOPICS
        ]

        # --- PII: block sensitive PII outright. Name/email/URL are
        # deliberately absent from this config (see comment above
        # BLOCKED_PII_TYPES) so they pass through completely untouched. ---
        pii_entities_config = [
            bedrock.CfnGuardrail.PiiEntityConfigProperty(
                type=pii_type,
                action="BLOCK",
                input_action="BLOCK",
                output_action="BLOCK",
                input_enabled=True,
                output_enabled=True,
            )
            for pii_type in BLOCKED_PII_TYPES
        ]

        guardrail = bedrock.CfnGuardrail(
            self,
            "Guardrail",
            name=GUARDRAIL_NAME,
            description=(
                "Secretary chatbot guardrail: blocks jailbreaks, restricts "
                "conversation to career/background Q&A about Ian Koplowitz, "
                "blocks/anonymizes PII beyond the Knowledge Base."
            ),
            blocked_input_messaging=(
                "I can't help with that request. I'm here to answer questions "
                "about Ian Koplowitz's work history, skills, and projects."
            ),
            blocked_outputs_messaging=(
                "I'm not able to share that. Feel free to ask me about Ian "
                "Koplowitz's work history, skills, or projects instead."
            ),
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=content_filters,
            ),
            topic_policy_config=bedrock.CfnGuardrail.TopicPolicyConfigProperty(
                topics_config=topics_config,
            ),
            sensitive_information_policy_config=(
                bedrock.CfnGuardrail.SensitiveInformationPolicyConfigProperty(
                    pii_entities_config=pii_entities_config,
                )
            ),
        )

        # --- Pin a numbered, immutable version for production use. Per the
        # amazon-bedrock skill's guardrails reference: DRAFT is mutable and
        # must never be used in production guardrailConfig — a numbered
        # version guarantees the agent's behavior can't change silently out
        # from under it.
        #
        # IMPORTANT: CfnGuardrailVersion snapshots DRAFT at creation time and
        # CloudFormation only cuts a new version when THIS resource's own
        # properties change — updating the Guardrail's policy above does NOT
        # automatically produce a new version, since `guardrail_identifier`
        # and `description` are unchanged from CFN's point of view. Bump
        # `description` (e.g. note what changed) any time the policy above
        # changes, to force a new version — otherwise the running agent stays
        # pinned to the stale, pre-change version. ---
        guardrail_version = bedrock.CfnGuardrailVersion(
            self,
            "GuardrailVersion",
            guardrail_identifier=guardrail.attr_guardrail_id,
            description=(
                "v2: stop ANONYMIZE-masking NAME/EMAIL/URL, which redacted "
                "the bot's own subject out of its responses."
            ),
        )
        guardrail_version.node.add_dependency(guardrail)

        # NOTE (PII logging compliance gap, per amazon-bedrock skill):
        # Guardrails PII masking/blocking only applies to the live API
        # response. Unmasked original content (including any PII) is still
        # logged in plain text to CloudWatch Logs if Bedrock model invocation
        # logging is enabled. This stack does not configure invocation
        # logging, so there's nothing to remediate here yet — but if/when
        # invocation logging is turned on downstream, the log group should be
        # KMS-encrypted and access-restricted before doing so.

        CfnOutput(self, "GuardrailIdOutput", value=guardrail.attr_guardrail_id)
        CfnOutput(self, "GuardrailArnOutput", value=guardrail.attr_guardrail_arn)
        CfnOutput(
            self, "GuardrailVersionOutput", value=guardrail_version.attr_version
        )
