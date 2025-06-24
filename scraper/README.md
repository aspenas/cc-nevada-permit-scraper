# Clark County Permit Scraper

## Secure Credential Loading

This project uses **AWS Secrets Manager** for all sensitive credentials (such as database URLs and API keys). You do **not** need to store secrets in your `.env` file. The application will automatically fetch credentials from AWS at runtime if they are not present in the environment.

### How it works
- On startup, the config loader checks for `DATABASE_URL` in the environment or `.env` file.
- If not found, it fetches the secret from AWS Secrets Manager (using the secret name in `DB_SECRET_NAME`, default: `clark-county-permit-db`).
- The secret is expected to be a JSON object with keys like `DATABASE_URL`.
- AWS credentials are loaded from your AWS CLI profile or environment variables.

### Required Environment Variables
- `AWS_REGION` (default: `us-west-2`)
- `DB_SECRET_NAME` (default: `clark-county-permit-db`)
- (Optional) `DATABASE_URL` (overrides AWS secret if set)

### Example AWS Secret (JSON)
```json
{
  "DATABASE_URL": "postgresql://user:password@host:5432/dbname"
}
```

### Local Development
1. Configure your AWS CLI (`aws configure`) or set AWS credentials in your environment.
2. (Optional) Create a `.env` file to override any variables for local testing.
3. Run your scripts as normal. Credentials will be loaded securely.

---

## Docker & CI/CD Readiness

- The project is ready for containerization. Add a `Dockerfile` and use environment variables for secrets.
- In CI/CD, set AWS credentials as environment variables or use an IAM role.
- No secrets should be hardcoded or checked into version control.

---

## Test Scaffolding

- The codebase is structured for easy unit and integration testing.
- You can mock AWS Secrets Manager and the database for tests.
- Add your tests in a `tests/` directory and use `pytest` or your preferred framework.

---

## Example Usage

```python
from scraper.database.manager import DatabaseManager

db_manager = DatabaseManager()  # Uses AWS Secrets Manager for credentials
```

---

## Questions?
Open an issue or check the code comments for more details.

## Code Quality & Pre-commit Hooks

This project enforces code style, linting, and type checking using [pre-commit](https://pre-commit.com/) with Black, Ruff, and Mypy. All code must pass these checks before being committed.

### Setup
1. Install pre-commit if you haven't already:
   ```sh
   pip install pre-commit
   ```
2. Install the hooks:
   ```sh
   pre-commit install
   ```
3. (Optional) Run all hooks on all files:
   ```sh
   pre-commit run --all-files
   ```

## Deployment: Docker Compose & AWS ECS

### Local Development

1. Copy `.env.example` to `.env` and set your secrets (or export them in your shell).
2. Run:
   ```sh
   docker-compose up --build
   ```
   This will start both the scraper and a local Postgres database.

### AWS ECS/Cloud Deployment
- The provided `docker-compose.yml` is compatible with AWS ECS Compose-X and Copilot.
- Set your secrets in AWS Secrets Manager and configure the ECS task definition to inject them as environment variables.
- For production, use RDS/Postgres and set `DATABASE_URL` accordingly.

## Data/ML Pipeline Readiness
- The scraper is ready for integration with analytics and ML workflows.
- To enable S3 export, add logic to write results to an S3 bucket after scraping.
- For data validation, consider integrating Great Expectations or similar tools.
- For event-driven pipelines, use AWS Lambda, Step Functions, or S3 triggers to process new data as it arrives.

## Monitoring & Alerting (CloudWatch)

- **Logs**: All scraper logs are sent to AWS CloudWatch Log Group: `/aws/cc-nevada-permit-scraper/<env>`
  - Set `CLOUDWATCH_LOG_GROUP` env var to override log group name (optional).
- **Metrics**: Custom CloudWatch metrics are emitted for:
  - `PermitScrapeSuccess` (Count)
  - `PermitScrapeFailure` (Count)
  - `PermitScrapeDuration` (Seconds)
  - `PermitScrapeErrorCount` (Count)
- **Alarms**: CloudWatch alarms are set for:
  - 1+ permit scrape failures in 5 minutes
  - 3+ errors in 5 minutes
  - Alarms notify the SNS topic (`sns_alerts_topic_arn` output from Terraform)
- **Alerting**: Subscribe Slack/email endpoints to the SNS topic for real-time notifications.

See `terraform/README.md` for infra details and how to subscribe endpoints to the SNS topic.

### New Monitoring & Dashboard (2024-07)
- **CloudWatch Dashboard**: Visualizes scrape success/failure, error count, duration, and pod restarts.
  - Output: `cloudwatch_dashboard_url` (see Terraform outputs)
- **New Alarms**:
  - Pod restarts (>=1 in 5 min)
  - High scrape duration (>=5 min average in 5 min)
- All alarms notify the SNS topic for alerting (Slack, email, PagerDuty, etc.).

#### Dashboard Access
- Open the dashboard in AWS Console:
  - `${cloudwatch_dashboard_url}`

#### Customization
- Adjust alarm thresholds in `main.tf` as needed for your workload.

## Production Automation & Monitoring

- The scraper runs on EKS with IRSA (OIDC) for secure IAM role assumption.
- All secrets (DB, API keys) are stored in AWS Secrets Manager, encrypted with KMS.
- Monitoring and alerting are handled via CloudWatch and SNS.
- Deployments are managed via Terraform and Kubernetes manifests.
- For troubleshooting, check CloudWatch logs and SNS alerts.

## CI/CD and Automated Test Alerting

- All tests (including end-to-end) are run automatically on every push via GitHub Actions.
- If any test fails, an alert is sent to the SNS topic (`SNS_ALERTS_TOPIC_ARN`), which notifies Slack/email as configured in Terraform.
- This ensures production issues are caught and alerted before deployment.
- See `.github/workflows/ci.yml` for details.

# Operational Runbook

## Deployment
- Use `deploy_and_verify.sh` for full automated deployment and monitoring verification.
- This script provisions all infra, applies Kubernetes manifests, and verifies CloudWatch/SNS.

## Troubleshooting
- **Check CloudWatch logs** for errors or failures in `/aws/cc-nevada-permit-scraper/<env>`.
- **Check SNS alerts** (Slack/email) for real-time notifications of failures or test issues.
- **Check GitHub Actions** for CI/CD and test results.
- For secret or IAM issues, verify IRSA and Secrets Manager configuration in AWS Console.

## Incident Response
- If an alarm fires (SNS alert):
  1. Check CloudWatch logs for error details.
  2. Review recent deployments or code changes.
  3. If a test failure, see the linked GitHub Actions run for traceback.
  4. If the issue is infra-related, check Terraform state and AWS Console.
- **Escalation:**
  - If unable to resolve, escalate to the cloud/DevOps owner or open an issue in this repo.

# Disaster Recovery

## RDS Restore
1. Go to AWS RDS Console > Databases > Select your DB instance.
2. Click 'Actions' > 'Restore to point in time' or select a snapshot.
3. Launch a new DB instance from the snapshot.
4. Update the secret in AWS Secrets Manager with the new endpoint if needed.
5. Update the Kubernetes secret or environment variable if the endpoint changes.

## S3 Recovery
1. Go to AWS S3 Console > Buckets > Select your export bucket.
2. Use versioning to restore deleted/overwritten objects.
3. For large restores, use AWS CLI or S3 batch operations.

## EKS Node Group Restoration
1. If a node group fails, use Terraform to re-apply the node group resources:
   ```sh
   cd terraform
   terraform apply -target=aws_eks_node_group.scraper -auto-approve
   ```
2. Monitor pod status with:
   ```sh
   kubectl get pods -n default
   ```
3. If IRSA or IAM issues, verify the ServiceAccount and IAM role in AWS Console.

# Alarm & Dashboard Tuning

## Regular Review Process
- Review CloudWatch alarm thresholds and dashboard widgets monthly or after major changes.
- Use production metrics to adjust thresholds for scrape failures, errors, duration, and pod restarts.
- Update Terraform alarm resources and dashboard widgets as needed.
- Document any changes in the repo and notify the team.

## Automation
- Consider automating dashboard updates using scripts or Terraform data sources as your metrics evolve.

## New Monitoring & Dashboard (2024-07)
- **CloudWatch Dashboard**: Visualizes scrape success/failure, error count, duration, and pod restarts.
  - Output: `cloudwatch_dashboard_url` (see Terraform outputs)
- **New Alarms**:
  - Pod restarts (>=1 in 5 min)
  - High scrape duration (>=5 min average in 5 min)
- All alarms notify the SNS topic for alerting (Slack, email, PagerDuty, etc.).

#### Dashboard Access
- Open the dashboard in AWS Console:
  - `${cloudwatch_dashboard_url}`

#### Customization
- Adjust alarm thresholds in `main.tf` as needed for your workload. 