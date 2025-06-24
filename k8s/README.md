# Kubernetes (AWS EKS) Deployment

## Quick Start (Dev/Test)
1. Edit `scraper-secret.yaml` with your test secrets.
2. Deploy secrets and scraper:
   ```sh
   kubectl apply -f scraper-secret.yaml
   kubectl apply -f scraper-deployment.yaml
   ```

## Production (AWS EKS, IRSA, AWS Secrets Manager)
- Use [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) to grant your scraper pod access to AWS Secrets Manager.
- Do **not** store secrets in Kubernetes for production. Instead, fetch them at runtime (already supported in your code).
- Set `DB_SECRET_NAME` and `AWS_REGION` as environment variables in the deployment manifest.
- Use RDS/Postgres for the production database and update `DATABASE_URL` accordingly.

## Scheduled Scraping (CronJob)
- To run the scraper automatically on a schedule (e.g., daily at 2am UTC):
  ```sh
  kubectl apply -f scraper-cronjob.yaml
  ```
- Edit the `schedule` field in `scraper-cronjob.yaml` to customize timing.
- For event-driven or S3-export pipelines, add hooks in the scraper or use AWS Lambda/S3 triggers.

## Notes
- The provided manifests are a starting point. Adjust resources, replicas, and namespaces as needed.
- For scheduled scraping, use a Kubernetes CronJob instead of a Deployment. 