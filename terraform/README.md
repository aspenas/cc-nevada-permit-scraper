# Terraform: Full AWS Stack for cc-nevada-permit-scraper

## What This Provisions
- S3 bucket for scraper exports
- RDS Postgres database
- Secrets Manager secret for DB credentials
- IAM role and policy for EKS IRSA (or ECS)
- CloudWatch log group for scraper logs
- SNS topic for monitoring/alerting (Slack/email integration)

## Prerequisites
- [Terraform](https://www.terraform.io/downloads.html) >= 1.3
- AWS CLI configured with sufficient permissions
- (For EKS IRSA) OIDC provider ARN and URL for your EKS cluster

## Usage
```sh
cd terraform
terraform init
terraform apply -var="eks_oidc_provider_arn=arn:aws:iam::<account>:oidc-provider/oidc.eks.<region>.amazonaws.com/id/<id>" \
                -var="eks_oidc_provider_url=oidc.eks.<region>.amazonaws.com/id/<id>"
```

## Outputs
- `s3_export_bucket`: Name of the S3 bucket for exports
- `rds_endpoint`: RDS Postgres endpoint
- `secretsmanager_arn`: ARN of the DB credentials secret
- `irsa_role_arn`: IAM role ARN for EKS service account
- `sns_alerts_topic_arn`: ARN of the SNS topic for monitoring/alerting

## Connecting to Your Scraper
- Set `S3_EXPORT_BUCKET` env var to the output bucket name
- Use IRSA to grant your scraper pod access to S3 and Secrets Manager
- Set `DB_SECRET_NAME` to the output secret name
- Use the RDS endpoint for your `DATABASE_URL`

## Notes
- Adjust instance sizes, VPC, and security group settings as needed for production.
- For ECS, attach the IAM role to your task definition instead of IRSA.

## Monitoring & Alerting
- Scraper logs are sent to CloudWatch Log Group: `/aws/cc-nevada-permit-scraper/<env>`
- Alerts (job failures, errors, etc.) can be sent via the SNS topic: `sns_alerts_topic_arn` output
- Subscribe your Slack/email endpoint to the SNS topic for notifications

## SNS Alerting Setup

- To receive alerts, subscribe your Slack or email endpoint to the SNS topic output as `sns_alerts_topic_arn`.
- Example (email):
  1. Go to AWS SNS console > Topics > select your topic.
  2. Click 'Create subscription'.
  3. Protocol: `email`, Endpoint: your@email.com.
  4. Confirm the subscription via email.
- Example (Slack):
  - Use an AWS Lambda or third-party integration to relay SNS messages to Slack webhook.
  - See: https://docs.aws.amazon.com/sns/latest/dg/sns-send-message-to-slack.html

## CloudWatch Alarms
- Alarms for permit scrape failures and high error rates are wired to the SNS topic for real-time alerting.

## OIDC Provider Variables

Add the following to your terraform.tfvars or environment:

```
eks_oidc_provider_url = "https://oidc.eks.us-west-2.amazonaws.com/id/C0F23AD6C61A174278A5A674648A08A4"
eks_oidc_provider_arn = "<your-oidc-provider-arn>"
```

## Best Practices
- All secrets must be stored in AWS Secrets Manager, encrypted with KMS.
- Never hardcode secrets or credentials in code or Terraform files.
- Use Terraform data sources to reference secrets and KMS keys.
- All infra changes must be applied via `terraform plan` and `terraform apply`.

## New Monitoring & Dashboard (2024-07)

- **CloudWatch Dashboard**: Visualizes scrape success/failure, error count, duration, and pod restarts.
  - Output: `cloudwatch_dashboard_url`
- **New Alarms**:
  - Pod restarts (>=1 in 5 min)
  - High scrape duration (>=5 min average in 5 min)
- All alarms notify the SNS topic for alerting (Slack, email, PagerDuty, etc.).

### Dashboard Access
- Open the dashboard in AWS Console:
  - `${cloudwatch_dashboard_url}`

### Customization
- Adjust alarm thresholds in `main.tf` as needed for your workload.

<!-- Triggered by fullauto verification at 2024-07-09T00:00:00Z --> 