resource "aws_secretsmanager_secret" "anthropic_key" {
  name = "${local.name_prefix}/anthropic-api-key"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "anthropic_key" {
  secret_id     = aws_secretsmanager_secret.anthropic_key.id
  secret_string = var.anthropic_api_key
}

resource "aws_secretsmanager_secret" "openai_key" {
  name = "${local.name_prefix}/openai-api-key"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "openai_key" {
  secret_id     = aws_secretsmanager_secret.openai_key.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "tavily_key" {
  name = "${local.name_prefix}/tavily-api-key"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "tavily_key" {
  secret_id     = aws_secretsmanager_secret.tavily_key.id
  secret_string = var.tavily_api_key
}

resource "aws_secretsmanager_secret" "langchain_key" {
  name = "${local.name_prefix}/langchain-api-key"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "langchain_key" {
  secret_id     = aws_secretsmanager_secret.langchain_key.id
  secret_string = var.langchain_api_key
}

resource "aws_secretsmanager_secret" "rds_password" {
  name = "${local.name_prefix}/rds-password"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id     = aws_secretsmanager_secret.rds_password.id
  secret_string = var.rds_password
}
