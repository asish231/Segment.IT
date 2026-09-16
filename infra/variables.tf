variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "project" {
  type    = string
  default = "bhoomiai"
}

variable "environment" {
  type    = string
  default = "production"
}

# --- GitHub OIDC (for CD workflow) ---
variable "github_org" {
  description = "GitHub org/user that owns the repo, e.g. \"asish231\""
  type        = string
}

variable "github_repo" {
  description = "Repo name, e.g. \"ocr\""
  type        = string
}

# --- App secrets (set via -var or a .tfvars file that is NOT committed) ---
variable "db_password" {
  type      = string
  sensitive = true
}

variable "secret_key" {
  description = "JWT signing secret. Generate with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
  type        = string
  sensitive   = true
}

variable "admin_email" {
  type    = string
  default = ""
}

variable "admin_password" {
  type      = string
  sensitive = true
  default   = ""
}

variable "mercury_api_key" {
  description = "Inception Labs Mercury-2.5 API key for LLM refinement"
  type        = string
  sensitive   = true
  default     = ""
}

# --- Sizing ---
variable "api_cpu" {
  type    = number
  default = 1024
}

variable "api_memory" {
  type    = number
  default = 4096
}

variable "web_cpu" {
  type    = number
  default = 256
}

variable "web_memory" {
  type    = number
  default = 512
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "web_desired_count" {
  type    = number
  default = 1
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}
