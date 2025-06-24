output "s3_export_bucket" {
  value = aws_s3_bucket.export.bucket
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "secretsmanager_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "irsa_role_arn" {
  value = aws_iam_role.scraper.arn
}

output "cloudwatch_log_group_name" {
  value = aws_cloudwatch_log_group.scraper.name
}

output "sns_alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "kms_secrets_arn" {
  value = aws_kms_key.secrets.arn
}

output "slack_webhook_secret_arn" {
  value = aws_secretsmanager_secret.slack_webhook.arn
}

output "cloudwatch_dashboard_name" {
  value = aws_cloudwatch_dashboard.scraper.dashboard_name
}

output "cloudwatch_dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.scraper.dashboard_name}"
} 