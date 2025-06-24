# Clark County Permit Scraper — Production Cloud Automation

[![codecov](https://codecov.io/gh/aspenas/cc-nevada-permit-scraper/branch/main/graph/badge.svg)](https://codecov.io/gh/aspenas/cc-nevada-permit-scraper)

## Project Overview

This repository contains a fully automated, production-grade cloud scraper stack for Clark County permits, running on AWS EKS with IRSA, KMS, Secrets Manager, Lambda, CloudWatch, and SNS. All infrastructure is managed via Terraform, with no hardcoded secrets.

- **Scraper code, automation, and operational runbook:** See [`scraper/README.md`](scraper/README.md)
- **Infrastructure, alerting, and monitoring runbook:** See [`terraform/README.md`](terraform/README.md)

## Quick Start
- For deployment and verification, use `deploy_and_verify.sh`.
- For troubleshooting, monitoring, and alerting, see the runbooks above. 