variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name — used as prefix for all resource names"
  type        = string
  default     = "dealflow-agent"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

# ── Networking ─────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs to use (must be >= 2)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ, hosts ALB)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ, hosts ECS + RDS)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

# ── ALB / HTTPS ────────────────────────────────────────────────────────────────

variable "acm_certificate_arn" {
  description = "ARN of an ACM certificate for the ALB HTTPS listener. Must be in the same region."
  type        = string
}

# ── ECS ────────────────────────────────────────────────────────────────────────

variable "container_port" {
  description = "Port the FastAPI container listens on"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "ECS task CPU units (256 | 512 | 1024 | 2048 | 4096)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 1024
}

variable "app_desired_count" {
  description = "Number of ECS task replicas"
  type        = number
  default     = 1
}

variable "app_image_tag" {
  description = "Docker image tag to deploy (e.g. git SHA)"
  type        = string
  default     = "latest"
}

# ── RDS ────────────────────────────────────────────────────────────────────────

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_allocated_storage_gb" {
  description = "Initial RDS storage in GB"
  type        = number
  default     = 20
}

variable "rds_db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "dealflow"
}

variable "rds_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "dealflow"
}

variable "rds_password" {
  description = "PostgreSQL master password — stored in Secrets Manager"
  type        = string
  sensitive   = true
}

# ── GitHub Actions OIDC ────────────────────────────────────────────────────────

variable "github_repo" {
  description = "GitHub repository in org/repo format (e.g. acme/dealflow-agent)"
  type        = string
}

variable "github_deploy_branch" {
  description = "Branch that is allowed to trigger deployments"
  type        = string
  default     = "main"
}

# ── Secrets ────────────────────────────────────────────────────────────────────

variable "anthropic_api_key" {
  description = "Anthropic API key — written to Secrets Manager, never stored in task def plaintext"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key for embeddings — written to Secrets Manager"
  type        = string
  sensitive   = true
}

variable "tavily_api_key" {
  description = "Tavily API key for MarketResearchAgent web search — written to Secrets Manager"
  type        = string
  sensitive   = true
  default     = ""
}

variable "langchain_api_key" {
  description = "LangSmith API key for tracing — optional, written to Secrets Manager"
  type        = string
  sensitive   = true
  default     = ""
}
