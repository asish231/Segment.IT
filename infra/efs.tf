# Shared job storage across api tasks (JOBS_DIR). Fargate's own disk is
# ephemeral and per-task, so with >1 api task the crops/documents need to live
# somewhere shared — EFS mounted at /app/data/jobs on every task.

resource "aws_efs_file_system" "jobs" {
  creation_token   = "${local.name}-jobs"
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"
  tags             = local.tags
}

resource "aws_efs_mount_target" "jobs" {
  for_each        = toset(data.aws_subnets.default.ids)
  file_system_id  = aws_efs_file_system.jobs.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "jobs" {
  file_system_id = aws_efs_file_system.jobs.id
  posix_user {
    uid = 0
    gid = 0
  }
  root_directory {
    path = "/jobs"
    creation_info {
      owner_uid   = 0
      owner_gid   = 0
      permissions = "0755"
    }
  }
  tags = local.tags
}
