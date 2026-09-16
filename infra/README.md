# Deploying BhoomiAI to AWS

Terraform for a first production deployment: ECR, ECS Fargate (api + web),
RDS Postgres, EFS (shared job storage), an internet-facing ALB, and the IAM
role GitHub Actions needs to deploy without storing AWS keys.

Architecture: only the `web` (nginx) task is public, behind the ALB. It
reverse-proxies `/segment`, `/jobs`, `/auth`, `/v1`, `/health` to the `api`
task over a private Cloud Map DNS name (`api.bhoomiai.local`) — the api task
is never reachable from the internet directly.

This is a starting point, not a hardened final architecture. It deliberately
uses the account's **default VPC** (public subnets, no NAT gateway) to keep
the first deploy simple. Follow-ups once this is working:
- Move to private subnets + NAT gateway (or VPC endpoints for ECR/Secrets
  Manager/CloudWatch) so tasks don't need public IPs.
- Attach a domain + ACM certificate, add an HTTPS listener, redirect :80 to :443.
- Autoscaling policies on the ECS services (target tracking on CPU/ALB request count).
- A WAF in front of the ALB.

## One-time setup

1. **State bucket** (do this once, manually or with a tiny separate
   Terraform config — it can't create the bucket it stores its own state in):
   ```
   aws s3api create-bucket --bucket bhoomiai-terraform-state --region ap-south-1 \
     --create-bucket-configuration LocationConstraint=ap-south-1
   aws s3api put-bucket-versioning --bucket bhoomiai-terraform-state \
     --versioning-configuration Status=Enabled
   ```
   Then uncomment the `backend "s3"` block in `versions.tf`.

2. **Variables** — copy `terraform.tfvars.example` to `terraform.tfvars` and fill
   it in (never commit `terraform.tfvars` — it holds secrets).

3. **Apply**:
   ```
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

4. **First image push** — the ECS services are created pointing at `:latest`
   tags that don't exist yet, so the first deploy will sit with 0 running
   tasks until you push once manually:
   ```
   aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
   docker build -t <account>.dkr.ecr.<region>.amazonaws.com/bhoomiai-production-api:latest .
   docker push <account>.dkr.ecr.<region>.amazonaws.com/bhoomiai-production-api:latest
   docker build -t <account>.dkr.ecr.<region>.amazonaws.com/bhoomiai-production-web:latest ./frontend
   docker push <account>.dkr.ecr.<region>.amazonaws.com/bhoomiai-production-web:latest
   aws ecs update-service --cluster bhoomiai-production --service bhoomiai-production-api --force-new-deployment
   aws ecs update-service --cluster bhoomiai-production --service bhoomiai-production-web --force-new-deployment
   ```
   After that, pushes to `main` handle this via `.github/workflows/cd.yml`.

5. **Wire up GitHub Actions** — in the repo's Settings → Secrets and variables →
   Actions → Variables, set:
   ```
   AWS_REGION       = <terraform output: var.aws_region>
   AWS_ROLE_ARN     = <terraform output: github_actions_role_arn>
   ECR_API_REPO     = <terraform output: ecr_api_repo>
   ECR_WEB_REPO     = <terraform output: ecr_web_repo>
   ECS_CLUSTER      = <terraform output: ecs_cluster>
   ECS_API_SERVICE  = <terraform output: ecs_api_service>
   ECS_WEB_SERVICE  = <terraform output: ecs_web_service>
   ```

6. **Migrations** — this app currently creates its schema with
   `Base.metadata.create_all()` on startup (see `db.py`). That's fine to get
   started; once the schema needs a real migration, switch to running
   `alembic upgrade head` as a one-off ECS task before rolling out the new
   service revision, rather than relying on create_all.

## Cost note

Default sizing (`variables.tf`) is deliberately small: 1 api task
(1 vCPU / 4 GB — the OCR/LLM pipeline is memory-hungry), 1 web task
(0.25 vCPU / 0.5 GB), `db.t4g.micro`. Fine for a pilot; raise
`api_desired_count`/`db_instance_class` for real load.
