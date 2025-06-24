terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }
  }
  required_version = ">= 1.3.0"
}

provider "aws" {
  region = var.aws_region
}

variable "project" { default = "cc-nevada-permit" }
variable "environment" { default = "prod" }
variable "aws_region" { default = "us-west-2" }

# S3 bucket for exports
resource "aws_s3_bucket" "export" {
  bucket = "${var.project}-export-${var.environment}"
  force_destroy = true
}

# RDS Postgres
resource "aws_db_instance" "main" {
  identifier = "${var.project}-db-${var.environment}"
  engine = "postgres"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  username = "scraper"
  password = random_password.db_password.result
  db_name = "scraperdb"
  skip_final_snapshot = true
  publicly_accessible = false
  vpc_security_group_ids = [aws_security_group.db.id]
  backup_retention_period = 7
  multi_az = true
}

resource "random_password" "db_password" {
  length  = 16
  special = true
}

resource "aws_security_group" "db" {
  name        = "${var.project}-db-sg-${var.environment}"
  description = "Allow Postgres access from EKS"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_vpc" "default" {
  default = true
}

# Secrets Manager for DB credentials
resource "aws_secretsmanager_secret" "db" {
  name = "${var.project}-db-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id     = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = aws_db_instance.main.username,
    password = aws_db_instance.main.password,
    host     = aws_db_instance.main.address,
    port     = aws_db_instance.main.port,
    dbname   = aws_db_instance.main.db_name
  })
}

# IAM role for EKS IRSA
resource "aws_iam_role" "scraper" {
  name = "${var.project}-irsa-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa.json
}

data "aws_iam_policy_document" "irsa" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = [var.eks_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.eks_oidc_provider_url}:sub"
      values   = ["system:serviceaccount:default:scraper"]
    }
  }
}

# IAM policy for S3 and Secrets access
resource "aws_iam_policy" "scraper" {
  name   = "${var.project}-policy-${var.environment}"
  policy = data.aws_iam_policy_document.scraper.json
}

data "aws_iam_policy_document" "scraper" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.export.arn,
      "${aws_s3_bucket.export.arn}/*"
    ]
  }
  statement {
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = [aws_secretsmanager_secret.db.arn]
  }
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "cloudwatch:PutMetricData"
    ]
    resources = [aws_cloudwatch_log_group.scraper.arn]
  }
}

resource "aws_iam_role_policy_attachment" "scraper" {
  role       = aws_iam_role.scraper.name
  policy_arn = aws_iam_policy.scraper.arn
}

# CloudWatch Log Group for scraper logs
resource "aws_cloudwatch_log_group" "scraper" {
  name              = "/aws/cc-nevada-permit-scraper/${var.environment}"
  retention_in_days = 30
}

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "cc-nevada-permit-alerts-${var.environment}"
}

# CloudWatch Alarm: Permit Scrape Failures (>=1 in 5 min)
resource "aws_cloudwatch_metric_alarm" "scrape_failure" {
  alarm_name          = "cc-nevada-permit-scrape-failure-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PermitScrapeFailure"
  namespace           = "ClarkCounty/Scraper"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "1 or more permit scrape failures in 5 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# CloudWatch Alarm: High Error Count (>=3 in 5 min)
resource "aws_cloudwatch_metric_alarm" "scrape_error_count" {
  alarm_name          = "cc-nevada-permit-scrape-error-high-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PermitScrapeErrorCount"
  namespace           = "ClarkCounty/Scraper"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 3
  alarm_description   = "3 or more errors in 5 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# KMS Key for Secrets Encryption
resource "aws_kms_key" "secrets" {
  description             = "KMS key for encrypting secrets (Slack webhook, etc.)"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# Secrets Manager for Slack Webhook (encrypted with KMS)
resource "aws_secretsmanager_secret" "slack_webhook" {
  name       = "slack-webhook-url"
  kms_key_id = aws_kms_key.secrets.arn
}

# Lambda IAM Role for SNS-to-Slack
resource "aws_iam_role" "sns_to_slack_lambda" {
  name = "sns-to-slack-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "sns_to_slack_lambda" {
  name = "sns-to-slack-lambda-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = [aws_secretsmanager_secret.slack_webhook.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sns_to_slack_lambda" {
  role       = aws_iam_role.sns_to_slack_lambda.name
  policy_arn = aws_iam_policy.sns_to_slack_lambda.arn
}

# Lambda function code (inline for now)
data "archive_file" "sns_to_slack_lambda_zip" {
  type        = "zip"
  source_dir  = "../lambda/sns_to_slack"
  output_path = "../lambda/sns_to_slack.zip"
}

resource "aws_lambda_function" "sns_to_slack" {
  function_name = "sns-to-slack"
  role          = aws_iam_role.sns_to_slack_lambda.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  filename      = data.archive_file.sns_to_slack_lambda_zip.output_path
  timeout       = 30
  environment {
    variables = {
      SLACK_SECRET_NAME = "slack-webhook-url"
    }
  }
  depends_on = [aws_secretsmanager_secret.slack_webhook]
  dead_letter_config {
    target_arn = aws_sqs_queue.sns_to_slack_dlq.arn
  }
}

# SNS subscription for Lambda
resource "aws_sns_topic_subscription" "slack_lambda" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.sns_to_slack.arn
}

resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sns_to_slack.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}

# --- CloudWatch Metric Filter: Pod Restarts ---
resource "aws_cloudwatch_log_metric_filter" "pod_restarts" {
  name           = "scraper-pod-restarts"
  log_group_name = aws_cloudwatch_log_group.scraper.name
  pattern        = "Restarting container"
  metric_transformation {
    name      = "PodRestarts"
    namespace = "ClarkCounty/Scraper"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "pod_restarts" {
  alarm_name          = "cc-nevada-permit-pod-restarts-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PodRestarts"
  namespace           = "ClarkCounty/Scraper"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "1 or more pod restarts in 5 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# --- CloudWatch Alarm: High Scrape Duration ---
resource "aws_cloudwatch_metric_alarm" "scrape_duration_high" {
  alarm_name          = "cc-nevada-permit-scrape-duration-high-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PermitScrapeDuration"
  namespace           = "ClarkCounty/Scraper"
  period              = 300 # 5 minutes
  statistic           = "Average"
  threshold           = 300 # 5 minutes
  alarm_description   = "Average permit scrape duration >= 5 minutes in 5 min window"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# --- CloudWatch Dashboard ---
resource "aws_cloudwatch_dashboard" "scraper" {
  dashboard_name = "cc-nevada-permit-scraper-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        "type": "metric",
        "x": 0, "y": 0, "width": 12, "height": 6,
        "properties": {
          "metrics": [
            [ "ClarkCounty/Scraper", "PermitScrapeSuccess" ],
            [ ".", "PermitScrapeFailure" ],
            [ ".", "PermitScrapeErrorCount" ]
          ],
          "period": 300,
          "stat": "Sum",
          "title": "Scrape Success/Failure/Error Count"
        }
      },
      {
        "type": "metric",
        "x": 0, "y": 6, "width": 12, "height": 6,
        "properties": {
          "metrics": [
            [ "ClarkCounty/Scraper", "PermitScrapeDuration" ]
          ],
          "period": 300,
          "stat": "Average",
          "title": "Scrape Duration (Seconds)"
        }
      },
      {
        "type": "metric",
        "x": 0, "y": 12, "width": 12, "height": 6,
        "properties": {
          "metrics": [
            [ "ClarkCounty/Scraper", "PodRestarts" ]
          ],
          "period": 300,
          "stat": "Sum",
          "title": "Pod Restarts"
        }
      }
    ]
  })
}

# --- RDS Automated Backups ---

# --- S3 Versioning and Lifecycle ---
resource "aws_s3_bucket_versioning" "export" {
  bucket = aws_s3_bucket.export.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_lifecycle_configuration" "export" {
  bucket = aws_s3_bucket.export.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# --- RDS Snapshot Retention ---
# (Handled by backup_retention_period above)

# --- Secrets Manager Rotation ---
resource "aws_secretsmanager_secret_rotation" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  rotation_lambda_arn = aws_lambda_function.db_rotation.arn
  rotation_rules {
    automatically_after_days = 30
  }
}

# --- Lambda DLQ ---
resource "aws_sqs_queue" "sns_to_slack_dlq" {
  name = "sns-to-slack-dlq"
}

# --- EKS Managed Node Group with Spot/Autoscaling ---
resource "aws_eks_node_group" "scraper" {
  cluster_name    = var.eks_cluster_name
  node_group_name = "scraper-prod"
  node_role_arn   = var.eks_node_role_arn
  subnet_ids      = var.eks_subnet_ids

  scaling_config {
    desired_size = var.eks_node_desired_size
    max_size     = var.eks_node_max_size
    min_size     = var.eks_node_min_size
  }

  instance_types = var.eks_node_instance_types

  capacity_type = "SPOT"

  labels = {
    role = "scraper"
    env  = var.environment
  }

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name        = "scraper-prod"
    Environment = var.environment
    Project     = var.project
  }
}

# Optionally, add a small on-demand node group for critical workloads
resource "aws_eks_node_group" "scraper_ondemand" {
  cluster_name    = var.eks_cluster_name
  node_group_name = "scraper-prod-ondemand"
  node_role_arn   = var.eks_node_role_arn
  subnet_ids      = var.eks_subnet_ids

  scaling_config {
    desired_size = 1
    max_size     = 2
    min_size     = 1
  }

  instance_types = [var.eks_node_ondemand_instance_type]
  capacity_type  = "ON_DEMAND"

  labels = {
    role = "scraper-ondemand"
    env  = var.environment
  }

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name        = "scraper-prod-ondemand"
    Environment = var.environment
    Project     = var.project
  }
}

# --- IAM Policy Tightening ---
# Restrict IRSA to only S3 and Secrets Manager for the specific resources
# Restrict Lambda to only logs and the specific secret
# ... existing code ...

resource "aws_lambda_function" "db_rotation" {
  function_name = "db-secret-rotation"
  role          = aws_iam_role.sns_to_slack_lambda.arn
  handler       = "db_rotation.lambda_handler"
  runtime       = "python3.11"
  filename      = "../lambda/db_rotation.zip"
  timeout       = 30
  environment {
    variables = {
      DB_SECRET_ARN = aws_secretsmanager_secret.db.arn
      DB_INSTANCE_ID = aws_db_instance.main.id
      AWS_REGION = var.aws_region
    }
  }
}

resource "aws_iam_policy" "db_rotation" {
  name = "db-rotation-lambda-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue"
        ],
        Resource = aws_secretsmanager_secret.db.arn
      },
      {
        Effect = "Allow",
        Action = [
          "rds:ModifyDBInstance"
        ],
        Resource = aws_db_instance.main.arn
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "db_rotation" {
  role       = aws_iam_role.sns_to_slack_lambda.name
  policy_arn = aws_iam_policy.db_rotation.arn
} 