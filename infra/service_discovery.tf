# Lets the web (nginx) task find the api task by DNS name inside the VPC,
# the same way docker-compose's network alias "api" works locally.

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = "${var.project}.local"
  vpc  = data.aws_vpc.default.id
  tags = local.tags
}

resource "aws_service_discovery_service" "api" {
  name = "api"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config {
    failure_threshold = 1
  }
}
