output "ecr_repository_url" {
  description = "ECR repository URL — use with docker tag + push"
  value       = aws_ecr_repository.app.repository_url
}

output "alb_dns_name" {
  description = "ALB DNS name — point your CNAME / Route53 alias here"
  value       = aws_lb.main.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name — used in GitHub Actions force-new-deployment"
  value       = aws_ecs_service.app.name
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port)"
  value       = "${aws_db_instance.main.address}:${aws_db_instance.main.port}"
}

output "github_deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC — set as AWS_ROLE_ARN in repo secrets"
  value       = aws_iam_role.github_deploy.arn
}
