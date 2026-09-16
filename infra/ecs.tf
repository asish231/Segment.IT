resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}/api"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${local.name}/web"
  retention_in_days = 14
  tags              = local.tags
}

# --- api task ---

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  volume {
    name = "jobs"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.jobs.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.jobs.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name         = "api"
    image        = "${aws_ecr_repository.api.repository_url}:latest"
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    mountPoints  = [{ sourceVolume = "jobs", containerPath = "/app/data/jobs" }]
    environment = [
      { name = "JOBS_DIR", value = "/app/data/jobs" },
      { name = "CORS_ORIGINS", value = "http://${aws_lb.this.dns_name}" },
      { name = "ACCESS_TOKEN_MINUTES", value = "60" },
      { name = "REFRESH_TOKEN_DAYS", value = "14" },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.api_env.arn}:DATABASE_URL::" },
      { name = "SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.api_env.arn}:SECRET_KEY::" },
      { name = "ADMIN_EMAIL", valueFrom = "${aws_secretsmanager_secret.api_env.arn}:ADMIN_EMAIL::" },
      { name = "ADMIN_PASSWORD", valueFrom = "${aws_secretsmanager_secret.api_env.arn}:ADMIN_PASSWORD::" },
      { name = "MERCURY_API_KEY", valueFrom = "${aws_secretsmanager_secret.api_env.arn}:MERCURY_API_KEY::" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])

  tags = local.tags
}

resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = true # default VPC has no NAT gateway; tasks need a public IP to pull images
  }

  service_registries {
    registry_arn = aws_service_discovery_service.api.arn
  }

  tags = local.tags
}

# --- web task ---

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.web_cpu
  memory                   = var.web_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name         = "web"
    image        = "${aws_ecr_repository.web.repository_url}:latest"
    portMappings = [{ containerPort = 80, protocol = "tcp" }]
    environment = [
      { name = "API_UPSTREAM", value = "api.${aws_service_discovery_private_dns_namespace.internal.name}:8000" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.web.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "web"
      }
    }
  }])

  tags = local.tags
}

resource "aws_ecs_service" "web" {
  name            = "${local.name}-web"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.web.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.http]
  tags       = local.tags
}
