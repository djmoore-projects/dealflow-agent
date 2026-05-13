variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name used as prefix for all resource names"
  type        = string
  default     = "dealflow-agent"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "container_port" {
  description = "Port the FastAPI container listens on"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "ECS task CPU units (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 1024
}

variable "anthropic_api_key" {
  description = "Anthropic API key — stored as ECS secret, never in plaintext"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key for embeddings"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "PostgreSQL connection string (must include pgvector-enabled RDS endpoint)"
  type        = string
  sensitive   = true
}
