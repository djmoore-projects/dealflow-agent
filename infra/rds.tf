resource "aws_db_subnet_group" "main" {
  name       = local.name_prefix
  subnet_ids = aws_subnet.private[*].id
  tags       = local.tags
}

# pg16 parameter group — pgvector is built-in from PostgreSQL 15+, no custom
# parameters needed; group ensures we stay on the right major version.
resource "aws_db_parameter_group" "pg16" {
  name   = "${local.name_prefix}-pg16"
  family = "postgres16"
  tags   = local.tags
}

resource "aws_db_instance" "main" {
  identifier = local.name_prefix

  engine               = "postgres"
  engine_version       = "16"
  instance_class       = var.rds_instance_class
  allocated_storage    = var.rds_allocated_storage_gb
  storage_type         = "gp3"
  storage_encrypted    = true

  db_name  = var.rds_db_name
  username = var.rds_username
  password = var.rds_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.pg16.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az               = false  # set true for production HA
  publicly_accessible    = false
  deletion_protection    = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "${local.name_prefix}-final"

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  performance_insights_enabled = true

  tags = local.tags
}
