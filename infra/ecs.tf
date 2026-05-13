resource "aws_ecs_cluster" "main" {
  name = local.name_prefix
  tags = local.tags

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = local.name_prefix
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "app"
    image     = "${aws_ecr_repository.app.repository_url}:${var.app_image_tag}"
    essential = true

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_key.arn },
      { name = "OPENAI_API_KEY",    valueFrom = aws_secretsmanager_secret.openai_key.arn },
      { name = "TAVILY_API_KEY",    valueFrom = aws_secretsmanager_secret.tavily_key.arn },
      { name = "LANGCHAIN_API_KEY", valueFrom = aws_secretsmanager_secret.langchain_key.arn },
    ]

    environment = [
      {
        name  = "DATABASE_URL"
        # Compose the connection string from RDS outputs — pgvector needs psycopg3 driver.
        value = "postgresql+psycopg://${var.rds_username}:${var.rds_password}@${aws_db_instance.main.address}:5432/${var.rds_db_name}"
      },
      { name = "CLAUDE_MODEL",        value = "claude-sonnet-4-20250514" },
      { name = "EMBEDDING_MODEL",     value = "text-embedding-3-small" },
      { name = "LOG_FORMAT",          value = "json" },
      { name = "LANGCHAIN_PROJECT",   value = "${var.app_name}-${var.environment}" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/${local.name_prefix}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
        "awslogs-create-group"  = "true"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }
  }])

  tags = local.tags
}

resource "aws_ecs_service" "app" {
  name            = local.name_prefix
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.app_desired_count
  launch_type     = "FARGATE"

  # Replace running tasks immediately on new deploy rather than waiting for
  # draining — keeps deployments fast for a single-replica staging setup.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.https]
  tags       = local.tags

  lifecycle {
    # image_tag changes arrive via ECS UpdateService — don't let Terraform
    # fight the GitHub Actions deploy by reverting to the last tf-known tag.
    ignore_changes = [task_definition]
  }
}
