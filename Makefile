.DEFAULT_GOAL := help

AWS_ACCOUNT ?= 107674771027
AWS_REGION ?= us-east-1
KB_STACK := KnowledgeBaseStack
GUARDRAIL_STACK := GuardrailStack
RUNTIME_STACK := RuntimeStack
LAMBDA_PROXY_STACK := LambdaProxyStack

export CDK_DEFAULT_ACCOUNT := $(AWS_ACCOUNT)
export CDK_DEFAULT_REGION := $(AWS_REGION)

DOCKER_IMAGE := secretary-agent:local
DOCKER_CONTAINER := secretary-agent-local
DOCKER_PORT ?= 8081

# Builds {"message": "..."} safely regardless of quotes/apostrophes in
# MESSAGE — hand-rolled shell quoting bit us once already (see deploy skill).
JSON_MESSAGE = python3 -c "import json,sys; print(json.dumps({'message': sys.argv[1]}))" "$(MESSAGE)"

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

## --- Frontend ---

.PHONY: frontend-install
frontend-install: ## Install frontend dependencies
	cd frontend && npm install

.PHONY: frontend-dev
frontend-dev: ## Run the frontend dev server (chat UI against a mock stream)
	cd frontend && npm run dev

.PHONY: frontend-test
frontend-test: ## Run frontend tests (Vitest)
	cd frontend && npm test -- --run

.PHONY: frontend-build
frontend-build: ## Build the frontend for production
	cd frontend && npm run build

## --- Agent (local CLI, root .venv) ---

.PHONY: agent-venv
agent-venv: ## (Re)build the root .venv used to run my_agent locally
	rm -rf .venv
	python3 -m venv .venv
	.venv/bin/pip install -r my_agent/requirements.txt

.PHONY: agent-run
agent-run: ## Run the agent CLI locally. Usage: make agent-run MESSAGE="..."
	.venv/bin/python -m my_agent.agent --message "$(MESSAGE)"

## --- Agent (Docker / AgentCore container, run locally) ---

.PHONY: docker-build
docker-build: ## Build the ARM64 AgentCore container image locally
	docker buildx build --platform linux/arm64 --load -t $(DOCKER_IMAGE) .

.PHONY: docker-run
docker-run: ## Run the container locally using YOUR OWN AWS creds (not the deployed execution role — see deploy skill's note on this)
	@eval "$$(aws configure export-credentials --format env-no-export)"; \
	KB_ID=$$(aws cloudformation describe-stacks --stack-name $(KB_STACK) --region $(AWS_REGION) --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" --output text); \
	GUARDRAIL_ID=$$(aws cloudformation describe-stacks --stack-name $(GUARDRAIL_STACK) --region $(AWS_REGION) --query "Stacks[0].Outputs[?OutputKey=='GuardrailIdOutput'].OutputValue" --output text); \
	GUARDRAIL_VERSION=$$(aws cloudformation describe-stacks --stack-name $(GUARDRAIL_STACK) --region $(AWS_REGION) --query "Stacks[0].Outputs[?OutputKey=='GuardrailVersionOutput'].OutputValue" --output text); \
	docker rm -f $(DOCKER_CONTAINER) >/dev/null 2>&1 || true; \
	docker run -d --platform linux/arm64 -p $(DOCKER_PORT):8080 \
		-e AWS_ACCESS_KEY_ID="$$AWS_ACCESS_KEY_ID" \
		-e AWS_SECRET_ACCESS_KEY="$$AWS_SECRET_ACCESS_KEY" \
		-e AWS_SESSION_TOKEN="$$AWS_SESSION_TOKEN" \
		-e AWS_REGION=$(AWS_REGION) \
		-e KNOWLEDGE_BASE_ID=$$KB_ID \
		-e GUARDRAIL_ID=$$GUARDRAIL_ID \
		-e GUARDRAIL_VERSION=$$GUARDRAIL_VERSION \
		-e DOCKER_CONTAINER=1 \
		--name $(DOCKER_CONTAINER) \
		$(DOCKER_IMAGE) >/dev/null; \
	echo "Running at http://localhost:$(DOCKER_PORT) -- try 'make docker-ping' or 'make docker-invoke MESSAGE=\"...\"'"

.PHONY: docker-ping
docker-ping: ## Health-check the locally running container
	curl -s http://localhost:$(DOCKER_PORT)/ping && echo

.PHONY: docker-invoke
docker-invoke: ## POST a message to the locally running container. Usage: make docker-invoke MESSAGE="..."
	@curl -s -X POST http://localhost:$(DOCKER_PORT)/invocations \
		-H "Content-Type: application/json" \
		-d "$$($(JSON_MESSAGE))"

.PHONY: docker-stop
docker-stop: ## Stop and remove the local test container
	docker rm -f $(DOCKER_CONTAINER)

## --- CDK / AWS deployment ---

.PHONY: infra-venv
infra-venv: ## (Re)build infra/.venv used for CDK's Python dependencies
	cd infra && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.PHONY: cdk-bootstrap
cdk-bootstrap: ## One-time CDK bootstrap for this account/region (already done for 107674771027/us-east-1 -- safe to re-run)
	cd infra && . .venv/bin/activate && cdk bootstrap aws://$(AWS_ACCOUNT)/$(AWS_REGION)

.PHONY: synth-kb
synth-kb: ## cdk synth KnowledgeBaseStack
	cd infra && . .venv/bin/activate && cdk synth $(KB_STACK)

.PHONY: synth-guardrail
synth-guardrail: ## cdk synth GuardrailStack
	cd infra && . .venv/bin/activate && cdk synth $(GUARDRAIL_STACK)

.PHONY: synth-runtime
synth-runtime: ## cdk synth RuntimeStack
	cd infra && . .venv/bin/activate && cdk synth $(RUNTIME_STACK)

.PHONY: synth-proxy
synth-proxy: ## cdk synth LambdaProxyStack
	cd infra && . .venv/bin/activate && cdk synth $(LAMBDA_PROXY_STACK)

.PHONY: synth-all
synth-all: ## cdk synth every stack
	cd infra && . .venv/bin/activate && cdk synth

.PHONY: deploy-kb
deploy-kb: ## Deploy KnowledgeBaseStack (S3 source bucket, S3 Vectors, Bedrock KB)
	cd infra && . .venv/bin/activate && cdk deploy $(KB_STACK) --require-approval never

.PHONY: deploy-guardrail
deploy-guardrail: ## Deploy GuardrailStack (Bedrock Guardrail)
	cd infra && . .venv/bin/activate && cdk deploy $(GUARDRAIL_STACK) --require-approval never

.PHONY: deploy-runtime
deploy-runtime: ## Deploy RuntimeStack (builds+pushes the Docker image, creates the AgentCore Runtime)
	cd infra && . .venv/bin/activate && cdk deploy $(RUNTIME_STACK) --require-approval never

.PHONY: deploy-proxy
deploy-proxy: ## Deploy LambdaProxyStack (streaming Function URL in front of AgentCore Runtime)
	cd infra && . .venv/bin/activate && cdk deploy $(LAMBDA_PROXY_STACK) --require-approval never

.PHONY: deploy-all
deploy-all: deploy-kb deploy-guardrail deploy-runtime deploy-proxy ## Deploy all four stacks in dependency order

.PHONY: reingest
reingest: ## Sync docs/kb-source/ to S3 and run a Bedrock KB ingestion job
	./scripts/reingest_kb.sh

.PHONY: invoke-runtime
invoke-runtime: ## Invoke the DEPLOYED AgentCore Runtime for real. Usage: make invoke-runtime MESSAGE="..."
	@ARN=$$(aws cloudformation describe-stacks --stack-name $(RUNTIME_STACK) --region $(AWS_REGION) --query "Stacks[0].Outputs[?OutputKey=='RuntimeArnOutput'].OutputValue" --output text); \
	aws bedrock-agentcore invoke-agent-runtime \
		--agent-runtime-arn "$$ARN" \
		--runtime-session-id "manual-$$(uuidgen | tr -d '-')" \
		--payload "$$($(JSON_MESSAGE))" \
		--cli-binary-format raw-in-base64-out \
		--region $(AWS_REGION) \
		/tmp/agentcore-invoke-output.txt; \
	cat /tmp/agentcore-invoke-output.txt

.PHONY: invoke-proxy
invoke-proxy: ## POST a message to the DEPLOYED Lambda Function URL. Usage: make invoke-proxy MESSAGE="..."
	@URL=$$(aws cloudformation describe-stacks --stack-name $(LAMBDA_PROXY_STACK) --region $(AWS_REGION) --query "Stacks[0].Outputs[?OutputKey=='FunctionUrlOutput'].OutputValue" --output text); \
	curl -N -X POST "$$URL" -H "Content-Type: application/json" -d "$$($(JSON_MESSAGE))"

## --- Teardown ---
## No `destroy-all` on purpose -- destructive actions stay one stack at a
## time, not a single blanket command. Destroy in reverse dependency order:
## LambdaProxyStack, then RuntimeStack, then GuardrailStack, then
## KnowledgeBaseStack.

.PHONY: destroy-proxy
destroy-proxy: ## Destroy LambdaProxyStack only
	cd infra && . .venv/bin/activate && cdk destroy $(LAMBDA_PROXY_STACK)

.PHONY: destroy-runtime
destroy-runtime: ## Destroy RuntimeStack only (destroy LambdaProxyStack first -- it depends on this)
	cd infra && . .venv/bin/activate && cdk destroy $(RUNTIME_STACK)

.PHONY: destroy-guardrail
destroy-guardrail: ## Destroy GuardrailStack only (destroy RuntimeStack first -- it depends on this)
	cd infra && . .venv/bin/activate && cdk destroy $(GUARDRAIL_STACK)

.PHONY: destroy-kb
destroy-kb: ## Destroy KnowledgeBaseStack only (destroy RuntimeStack first -- it depends on this)
	cd infra && . .venv/bin/activate && cdk destroy $(KB_STACK)
