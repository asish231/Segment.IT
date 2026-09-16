resource "aws_secretsmanager_secret" "api_env" {
  name = "${local.name}/api-env"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "api_env" {
  secret_id = aws_secretsmanager_secret.api_env.id
  secret_string = jsonencode({
    DATABASE_URL    = "postgresql+psycopg2://bhoomi:${var.db_password}@${aws_db_instance.postgres.address}:5432/bhoomi"
    SECRET_KEY      = var.secret_key
    ADMIN_EMAIL     = var.admin_email
    ADMIN_PASSWORD  = var.admin_password
    MERCURY_API_KEY = var.mercury_api_key
  })
}
