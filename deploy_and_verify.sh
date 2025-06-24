#!/bin/bash
set -euo pipefail

LOG=deploy_and_verify.log
exec > >(tee -a "$LOG") 2>&1

# OIDC provider values
OIDC_URL="https://oidc.eks.us-west-2.amazonaws.com/id/C0F23AD6C61A174278A5A674648A08A4"
OIDC_ARN="arn:aws:iam::207567767039:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/C0F23AD6C61A174278A5A674648A08A4"

# Write correct values to terraform.tfvars
TFVARS_FILE="terraform/terraform.tfvars"
echo "[INFO] Writing OIDC provider values to $TFVARS_FILE..."
cat > "$TFVARS_FILE" <<EOF
eks_oidc_provider_url = "$OIDC_URL"
eks_oidc_provider_arn = "$OIDC_ARN"
EOF

# Log for audit
cat "$TFVARS_FILE"

echo "[INFO] Starting full deployment and monitoring verification..."

# OIDC provider verification
echo "[INFO] OIDC Provider URL: $OIDC_URL"
echo "[INFO] OIDC Provider ARN: $OIDC_ARN"
echo "[INFO] Listing OIDC provider ARNs..."
OIDC_ARNS=$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[*].Arn" --output text)
echo "[INFO] OIDC Provider ARNs: $OIDC_ARNS"

# 1. Terraform apply
cd terraform

echo "[INFO] Running terraform init..."
terraform init

echo "[INFO] Running terraform plan..."
terraform plan -out=tfplan

echo "[INFO] Running terraform apply..."
terraform apply -auto-approve tfplan

echo "[INFO] Fetching Terraform outputs..."
LOG_GROUP=$(terraform output -raw cloudwatch_log_group_name)
SNS_TOPIC_ARN=$(terraform output -raw sns_alerts_topic_arn)
cd ..

echo "[INFO] Terraform apply complete."

# 2. Deploy Kubernetes manifests (if present)
if [ -d scraper/k8s ]; then
  echo "[INFO] Deploying Kubernetes manifests from scraper/k8s..."
  kubectl apply -f scraper/k8s/
else
  echo "[WARN] No Kubernetes manifests found in scraper/k8s. Skipping k8s deployment."
fi

echo "[INFO] Kubernetes deployment step complete."

# 3. Verify CloudWatch log group
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" | grep -q "$LOG_GROUP"; then
  echo "[OK] CloudWatch log group $LOG_GROUP exists."
else
  echo "[ERROR] CloudWatch log group $LOG_GROUP not found!"
fi

# 4. Verify SNS topic and send test message
if [ -n "$SNS_TOPIC_ARN" ]; then
  echo "[OK] SNS topic found: $SNS_TOPIC_ARN"
  echo "[INFO] Sending test message to SNS topic..."
  aws sns publish --topic-arn "$SNS_TOPIC_ARN" --message "[Test] Scraper deployment and monitoring verification at $(date)"
else
  echo "[ERROR] SNS topic ARN not found!"
fi

echo "[SUCCESS] Deployment and monitoring verification complete. Check CloudWatch and SNS for test events." 