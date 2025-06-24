# Terraform: Full AWS Stack for cc-nevada-permit-scraper

## What This Provisions
- S3 bucket for scraper exports
- RDS Postgres database
- Secrets Manager secret for DB credentials
- IAM role and policy for EKS IRSA (or ECS)

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

## Connecting to Your Scraper
- Set `S3_EXPORT_BUCKET` env var to the output bucket name
- Use IRSA to grant your scraper pod access to S3 and Secrets Manager
- Set `DB_SECRET_NAME` to the output secret name
- Use the RDS endpoint for your `DATABASE_URL`

## Notes
- Adjust instance sizes, VPC, and security group settings as needed for production.
- For ECS, attach the IAM role to your task definition instead of IRSA.

<!-- Triggered by fullauto verification at 2024-07-09T00:00:00Z --> 