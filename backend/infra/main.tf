resource "aws_kms_key" "uploads" {
  description             = "KMS key for appliance image uploads"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "uploads" {
  name          = "alias/${local.name_prefix}-uploads"
  target_key_id = aws_kms_key.uploads.key_id
}

resource "aws_kms_key" "database" {
  description             = "KMS key for Aurora PostgreSQL storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "database" {
  name          = "alias/${local.name_prefix}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_ecr_repository" "backend" {
  name                 = "${local.name_prefix}-backend"
  force_delete         = var.ecr_force_delete
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the most recent 30 backend images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb"
  description = "Internet-facing backend ALB"
  vpc_id      = var.vpc_id
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${local.name_prefix}-ecs-tasks"
  description = "Backend Fargate tasks"
  vpc_id      = var.vpc_id
}

resource "aws_security_group" "database" {
  name        = "${local.name_prefix}-database"
  description = "Aurora PostgreSQL access from backend tasks"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from the internet"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  ip_protocol       = "tcp"
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP redirect from the internet"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  ip_protocol       = "tcp"
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward traffic to API tasks"
  referenced_security_group_id = aws_security_group.ecs_tasks.id
  from_port                    = 8000
  ip_protocol                  = "tcp"
  to_port                      = 8000
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id            = aws_security_group.ecs_tasks.id
  description                  = "API traffic from ALB"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  ip_protocol                  = "tcp"
  to_port                      = 8000
}

#trivy:ignore:AVD-AWS-0104 Backend tasks need outbound HTTPS for AWS APIs, OpenAI, and Twilio; fixed third-party IP allowlists are not stable enough for this take-home.
#trivy:ignore:AWS-0104 Backend tasks need outbound HTTPS for AWS APIs, OpenAI, and Twilio; fixed third-party IP allowlists are not stable enough for this take-home.
resource "aws_vpc_security_group_egress_rule" "ecs_https" {
  security_group_id = aws_security_group.ecs_tasks.id
  description       = "Outbound HTTPS through NAT for AWS APIs, OpenAI, and Twilio"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  ip_protocol       = "tcp"
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "ecs_to_database" {
  security_group_id            = aws_security_group.ecs_tasks.id
  description                  = "Aurora PostgreSQL"
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "database_from_ecs" {
  security_group_id            = aws_security_group.database.id
  description                  = "PostgreSQL from backend tasks"
  referenced_security_group_id = aws_security_group.ecs_tasks.id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

#trivy:ignore:AVD-AWS-0053 Public ALB is required for Twilio webhooks, reviewer API smoke tests, and the public frontend.
#trivy:ignore:AWS-0053 Public ALB is required for Twilio webhooks, reviewer API smoke tests, and the public frontend.
resource "aws_lb" "api" {
  name                       = substr(replace("${local.name_prefix}-api", "-", ""), 0, 32)
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.public_subnet_ids
  drop_invalid_header_fields = true

  enable_deletion_protection = var.enable_alb_deletion_protection == null ? var.environment == "prod" : var.enable_alb_deletion_protection
}

resource "aws_lb_target_group" "api" {
  name        = substr(replace("${local.name_prefix}-api", "-", ""), 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/healthz"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

resource "aws_acm_certificate" "api" {
  domain_name               = var.api_domain_name
  subject_alternative_names = [var.ws_domain_name]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "api_certificate_validation" {
  provider = aws.dns
  for_each = {
    for option in aws_acm_certificate.api.domain_validation_options : option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.hosted_zone_id
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.api_certificate_validation : record.fqdn]
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate_validation.api.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_route53_record" "api" {
  provider = aws.dns
  zone_id  = var.hosted_zone_id
  name     = var.api_domain_name
  type     = "A"

  alias {
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "ws" {
  provider = aws.dns
  zone_id  = var.hosted_zone_id
  name     = var.ws_domain_name
  type     = "A"

  alias {
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
    evaluate_target_health = true
  }
}

resource "aws_db_subnet_group" "database" {
  name       = "${local.name_prefix}-database"
  subnet_ids = var.private_subnet_ids
}

resource "aws_rds_cluster" "database" {
  cluster_identifier           = "${local.name_prefix}-database"
  database_name                = var.database_name
  db_subnet_group_name         = aws_db_subnet_group.database.name
  deletion_protection          = var.database_deletion_protection
  engine                       = "aurora-postgresql"
  engine_mode                  = "provisioned"
  engine_version               = var.aurora_postgresql_engine_version
  final_snapshot_identifier    = var.database_skip_final_snapshot ? null : "${local.name_prefix}-database-final"
  kms_key_id                   = aws_kms_key.database.arn
  manage_master_user_password  = true
  master_username              = var.database_master_username
  skip_final_snapshot          = var.database_skip_final_snapshot
  storage_encrypted            = true
  vpc_security_group_ids       = [aws_security_group.database.id]
  backup_retention_period      = 7
  preferred_backup_window      = "07:00-09:00"
  preferred_maintenance_window = "sun:09:00-sun:10:00"

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity
    max_capacity = var.aurora_max_capacity
  }
}

resource "aws_rds_cluster_instance" "database" {
  count = 1

  cluster_identifier  = aws_rds_cluster.database.id
  engine              = aws_rds_cluster.database.engine
  engine_version      = aws_rds_cluster.database.engine_version
  instance_class      = "db.serverless"
  publicly_accessible = false
}

resource "aws_s3_bucket" "uploads" {
  bucket        = local.upload_bucket_name
  force_destroy = var.upload_bucket_force_destroy
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.uploads.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST", "GET", "HEAD"]
    allowed_origins = var.allowed_cors_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 300
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "expire-uploaded-images"
    status = "Enabled"

    filter {
      prefix = "diagnostic-sessions/"
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

resource "aws_sqs_queue" "vision_dlq" {
  name                      = "${local.name_prefix}-vision-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "vision" {
  name                       = "${local.name_prefix}-vision"
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 300
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.vision_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_ses_domain_identity" "email" {
  domain = var.email_domain
}

resource "aws_route53_record" "ses_verification" {
  provider = aws.dns
  zone_id  = var.hosted_zone_id
  name     = "_amazonses.${var.email_domain}"
  type     = "TXT"
  ttl      = 600
  records  = [aws_ses_domain_identity.email.verification_token]
}

resource "aws_ses_domain_identity_verification" "email" {
  domain = aws_ses_domain_identity.email.id

  depends_on = [aws_route53_record.ses_verification]
}

resource "aws_ses_domain_dkim" "email" {
  domain = aws_ses_domain_identity.email.domain
}

resource "aws_route53_record" "ses_dkim" {
  provider = aws.dns
  for_each = {
    for index in range(3) : tostring(index) => aws_ses_domain_dkim.email.dkim_tokens[index]
  }

  zone_id = var.hosted_zone_id
  name    = "${each.value}._domainkey.${var.email_domain}"
  type    = "CNAME"
  ttl     = 600
  records = ["${each.value}.dkim.amazonses.com"]
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  count = var.openai_api_key_secret_arn == null ? 1 : 0

  name                    = "/${local.name_prefix}/openai-api-key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "twilio_auth_token" {
  count = var.twilio_auth_token_secret_arn == null ? 1 : 0

  name                    = "/${local.name_prefix}/twilio-auth-token"
  recovery_window_in_days = 7
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/ecs/${local.name_prefix}/api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/ecs/${local.name_prefix}/worker"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "migration" {
  name              = "/aws/ecs/${local.name_prefix}/migration"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name_prefix}-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name = "read-runtime-secrets"
  role = aws_iam_role.task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_rds_cluster.database.master_user_secret[0].secret_arn,
          local.openai_api_key_secret_arn,
          local.twilio_auth_token_secret_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role" "api_task" {
  name = "${local.name_prefix}-api-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "api_task" {
  name = "application-access"
  role = aws_iam_role.api_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:ListBucketMultipartUploads"
        ]
        Resource = [
          aws_s3_bucket.uploads.arn,
          "${aws_s3_bucket.uploads.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.uploads.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.vision.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = aws_ses_domain_identity.email.arn
      }
    ]
  })
}

resource "aws_iam_role" "worker_task" {
  name = "${local.name_prefix}-worker-task"

  assume_role_policy = aws_iam_role.api_task.assume_role_policy
}

resource "aws_iam_role_policy" "worker_task" {
  name = "worker-access"
  role = aws_iam_role.worker_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.uploads.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.vision.arn
      }
    ]
  })
}

resource "aws_iam_role" "migration_task" {
  name = "${local.name_prefix}-migration-task"

  assume_role_policy = aws_iam_role.api_task.assume_role_policy
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  runtime_platform {
    cpu_architecture        = var.cpu_architecture
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.backend_image
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = local.application_environment
      secrets     = local.application_secrets
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  runtime_platform {
    cpu_architecture        = var.cpu_architecture
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name        = "worker"
      image       = local.backend_image
      essential   = true
      command     = ["python", "-m", "app.workers.vision", "--poll-sqs"]
      environment = local.application_environment
      secrets     = local.application_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name_prefix}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.migration_task.arn

  runtime_platform {
    cpu_architecture        = var.cpu_architecture
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name        = "migration"
      image       = local.backend_image
      essential   = true
      command     = ["alembic", "upgrade", "head"]
      environment = local.application_environment
      secrets = [
        {
          name      = "DATABASE_PASSWORD"
          valueFrom = local.database_password_secret_value_from
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.migration.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "migration"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = var.ecs_cluster_arn
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = var.private_subnet_ids
  }

  depends_on = [
    aws_lb_listener.https,
    aws_iam_role_policy.task_execution_secrets
  ]
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = var.ecs_cluster_arn
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    assign_public_ip = false
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = var.private_subnet_ids
  }

  depends_on = [aws_iam_role_policy.task_execution_secrets]
}
