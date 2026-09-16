output "app_url" {
  value = "http://${aws_lb.this.dns_name}"
}

output "ecr_api_repo" {
  value = aws_ecr_repository.api.name
}

output "ecr_web_repo" {
  value = aws_ecr_repository.web.name
}

output "ecs_cluster" {
  value = aws_ecs_cluster.this.name
}

output "ecs_api_service" {
  value = aws_ecs_service.api.name
}

output "ecs_web_service" {
  value = aws_ecs_service.web.name
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "db_endpoint" {
  value     = aws_db_instance.postgres.address
  sensitive = true
}
