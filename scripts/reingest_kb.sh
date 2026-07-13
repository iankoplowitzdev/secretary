#!/usr/bin/env bash
# Sync docs/kb-source/ to the KB's S3 bucket and run a Bedrock ingestion job.
# Usage: scripts/reingest_kb.sh
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="KnowledgeBaseStack"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/docs/kb-source"

outputs=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs' --output json)

bucket=$(echo "$outputs" | python3 -c "import json,sys; o={x['OutputKey']:x['OutputValue'] for x in json.load(sys.stdin)}; print(o['KbSourceBucketName'])")
kb_id=$(echo "$outputs" | python3 -c "import json,sys; o={x['OutputKey']:x['OutputValue'] for x in json.load(sys.stdin)}; print(o['KnowledgeBaseId'])")
ds_id=$(echo "$outputs" | python3 -c "import json,sys; o={x['OutputKey']:x['OutputValue'] for x in json.load(sys.stdin)}; print(o['KbDataSourceId'])")

echo "Bucket: s3://${bucket}"
echo "Knowledge Base: ${kb_id}  Data source: ${ds_id}"

echo "Syncing ${SOURCE_DIR} -> s3://${bucket}/ (excluding README.md, which is repo docs, not KB content)"
aws s3 sync "$SOURCE_DIR" "s3://${bucket}/" --exclude "README.md" --delete --region "$REGION"

echo "Starting ingestion job..."
job_id=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$kb_id" \
  --data-source-id "$ds_id" \
  --region "$REGION" \
  --query 'ingestionJob.ingestionJobId' --output text)

echo "Ingestion job ${job_id} started, polling..."
status="STARTING"
while [[ "$status" != "COMPLETE" && "$status" != "FAILED" ]]; do
  sleep 5
  status=$(aws bedrock-agent get-ingestion-job \
    --knowledge-base-id "$kb_id" \
    --data-source-id "$ds_id" \
    --ingestion-job-id "$job_id" \
    --region "$REGION" \
    --query 'ingestionJob.status' --output text)
  echo "  status: ${status}"
done

if [[ "$status" == "FAILED" ]]; then
  echo "Ingestion job failed:" >&2
  aws bedrock-agent get-ingestion-job \
    --knowledge-base-id "$kb_id" \
    --data-source-id "$ds_id" \
    --ingestion-job-id "$job_id" \
    --region "$REGION"
  exit 1
fi

echo "Ingestion complete. Statistics:"
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id "$kb_id" \
  --data-source-id "$ds_id" \
  --ingestion-job-id "$job_id" \
  --region "$REGION" \
  --query 'ingestionJob.statistics'
