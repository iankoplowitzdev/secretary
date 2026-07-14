from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_s3vectors as s3vectors,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_budgets as budgets,
)
from constructs import Construct

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024
BUDGET_ALERT_EMAIL = "iankoplowitzdev@gmail.com"
BUDGET_MONTHLY_LIMIT_USD = 25


class KnowledgeBaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        embedding_model_arn = (
            f"arn:aws:bedrock:{self.region}::foundation-model/{EMBEDDING_MODEL_ID}"
        )

        # --- Source document bucket ---
        source_bucket = s3.Bucket(
            self,
            "KbSourceBucket",
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- S3 Vectors backend (no idle/minimum charge, unlike OpenSearch Serverless) ---
        vector_bucket = s3vectors.CfnVectorBucket(
            self,
            "KbVectorBucket",
            vector_bucket_name="secretary-kb-vectors",
        )
        vector_index = s3vectors.CfnIndex(
            self,
            "KbVectorIndex",
            index_name="secretary-kb-index-v2",
            vector_bucket_name=vector_bucket.vector_bucket_name,
            data_type="float32",
            dimension=EMBEDDING_DIMENSION,
            distance_metric="cosine",
            # Bedrock stores each chunk's source text under this reserved metadata
            # key. Filterable metadata is capped at 2KB/vector in S3 Vectors, which
            # source text chunks can easily exceed, so it must be marked
            # non-filterable (we don't need to query on it, just retrieve it).
            metadata_configuration=s3vectors.CfnIndex.MetadataConfigurationProperty(
                non_filterable_metadata_keys=["AMAZON_BEDROCK_TEXT"],
            ),
        )
        vector_index.add_dependency(vector_bucket)

        # --- IAM role assumed by the Bedrock KB service ---
        kb_role = iam.Role(
            self,
            "KbServiceRole",
            role_name="AmazonBedrockExecutionRoleForKB-secretary",
            assumed_by=iam.ServicePrincipal(
                "bedrock.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/*"
                    },
                },
            ),
        )
        kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[embedding_model_arn],
            )
        )
        source_bucket.grant_read(kb_role)
        kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:PutVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                    "s3vectors:GetIndex",
                ],
                resources=[vector_index.attr_index_arn],
            )
        )

        # --- Knowledge Base ---
        knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name="secretary-knowledge-base-v2",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn,
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="S3_VECTORS",
                s3_vectors_configuration=bedrock.CfnKnowledgeBase.S3VectorsConfigurationProperty(
                    vector_bucket_arn=vector_bucket.attr_vector_bucket_arn,
                    index_arn=vector_index.attr_index_arn,
                ),
            ),
        )
        knowledge_base.node.add_dependency(kb_role)

        # --- Data source (S3, fixed-size chunking) ---
        data_source = bedrock.CfnDataSource(
            self,
            "KbDataSource",
            knowledge_base_id=knowledge_base.attr_knowledge_base_id,
            name="secretary-kb-source",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=source_bucket.bucket_arn,
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=300,
                        overlap_percentage=20,
                    ),
                ),
            ),
        )

        # --- Budget alarm on Bedrock spend (pulled forward from US-8) ---
        budgets.CfnBudget(
            self,
            "BedrockSpendBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name="secretary-bedrock-monthly-budget",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(
                    amount=BUDGET_MONTHLY_LIMIT_USD,
                    unit="USD",
                ),
                cost_filters={"Service": ["Amazon Bedrock"]},
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="ACTUAL",
                        threshold=80,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        budgets.CfnBudget.SubscriberProperty(
                            address=BUDGET_ALERT_EMAIL,
                            subscription_type="EMAIL",
                        )
                    ],
                ),
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="ACTUAL",
                        threshold=100,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        budgets.CfnBudget.SubscriberProperty(
                            address=BUDGET_ALERT_EMAIL,
                            subscription_type="EMAIL",
                        )
                    ],
                ),
            ],
        )

        # Exposed for cross-stack references within the same CDK app (e.g.
        # RuntimeStack, US-7).
        self.knowledge_base_id = knowledge_base.attr_knowledge_base_id
        self.knowledge_base_arn = knowledge_base.attr_knowledge_base_arn

        CfnOutput(self, "KbSourceBucketName", value=source_bucket.bucket_name)
        CfnOutput(self, "KnowledgeBaseId", value=knowledge_base.attr_knowledge_base_id)
        CfnOutput(self, "KbDataSourceId", value=data_source.attr_data_source_id)
