# DealFlow Agent — AWS Infrastructure

Terraform configuration for deploying DealFlow Agent to AWS Fargate.

## Architecture

```
Internet
   │
   ▼
 ALB (HTTPS/443 + HTTP→HTTPS redirect)
   │
   ▼
ECS Fargate (private subnet, FastAPI on :8000)
   │
   ├──► RDS PostgreSQL 16 + pgvector (private subnet)
   └──► Secrets Manager (API keys, injected at task start)
```

All compute runs in private subnets. A single NAT Gateway provides outbound
internet access for ECR image pulls and external API calls (Anthropic, OpenAI,
Tavily, LangSmith).

## File Structure

| File | Contents |
|------|----------|
| `main.tf` | Terraform + provider block, locals |
| `variables.tf` | All input variables with descriptions and defaults |
| `networking.tf` | VPC, subnets, IGW, NAT GW, security groups, ALB |
| `ecr.tf` | ECR repository + lifecycle policy |
| `iam.tf` | ECS execution role, GitHub Actions OIDC role |
| `secrets.tf` | Secrets Manager entries for all API keys |
| `rds.tf` | RDS PostgreSQL 16 + parameter group + subnet group |
| `ecs.tf` | ECS cluster, task definition, Fargate service |
| `outputs.tf` | ECR URL, ALB DNS, deploy role ARN, RDS endpoint |

## Prerequisites

1. AWS CLI configured with credentials that can create IAM roles, VPCs, ECR, ECS, RDS, and ALB.
2. An ACM certificate in the deployment region (for the ALB HTTPS listener).
3. The GitHub Actions OIDC provider must exist in your AWS account. Create it once:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --client-id-list sts.amazonaws.com
```

## First Deploy

```bash
cd infra

# 1. Create a tfvars file — never commit this
cat > prod.tfvars <<EOF
acm_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."
github_repo         = "your-org/dealflow-agent"
anthropic_api_key   = "sk-ant-..."
openai_api_key      = "sk-..."
tavily_api_key      = "tvly-..."
langchain_api_key   = "ls__..."
rds_password        = "$(openssl rand -base64 24)"
EOF

# 2. Initialise and preview
terraform init
terraform plan -var-file=prod.tfvars

# 3. Apply (creates VPC, RDS, ECS, ALB — takes ~10 min)
terraform apply -var-file=prod.tfvars

# 4. Push initial Docker image
ECR_URL=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password | docker login --username AWS --password-stdin "${ECR_URL}"
docker build -t "${ECR_URL}:latest" ..
docker push "${ECR_URL}:latest"

# 5. Force ECS to pull the image
aws ecs update-service \
  --cluster "$(terraform output -raw ecs_cluster_name)" \
  --service "$(terraform output -raw ecs_service_name)" \
  --force-new-deployment

# 6. Note the deploy role ARN for GitHub Actions
terraform output github_deploy_role_arn
```

## GitHub Actions Setup

Add the following repository secrets (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `AWS_ROLE_ARN` | Output of `terraform output -raw github_deploy_role_arn` |

Push to `main` to trigger the deploy workflow. The workflow:
1. Authenticates via OIDC (no long-lived AWS credentials)
2. Builds + pushes image tagged with the git SHA
3. Registers a new ECS task definition revision
4. Updates the ECS service and waits for stability
5. Hits `/health` via the ALB to confirm the deploy succeeded

## Updating After Initial Deploy

```bash
# Plan only the changed resources
terraform plan -var-file=prod.tfvars

terraform apply -var-file=prod.tfvars
```

After an `apply` that updates the task definition, force the service to pick it up:

```bash
aws ecs update-service \
  --cluster dealflow-agent-prod \
  --service dealflow-agent-prod \
  --force-new-deployment
```

## Destroying

```bash
# Disable deletion protection first
terraform apply -var-file=prod.tfvars \
  -target=aws_db_instance.main \
  -var="rds_deletion_protection=false"

terraform destroy -var-file=prod.tfvars
```
