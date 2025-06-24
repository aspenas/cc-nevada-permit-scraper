#!/bin/bash
set -euo pipefail

LOG=fix_aws_cli_env.log
exec > >(tee -a "$LOG") 2>&1

echo "[INFO] Diagnosing AWS CLI shell environment..."

# Check for aws alias
if alias aws 2>/dev/null; then
  echo "[WARN] 'aws' is aliased. Removing alias for this session."
  unalias aws
else
  echo "[OK] No 'aws' alias found."
fi

# Check for aws function
type aws | grep -q 'is a function' && {
  echo "[WARN] 'aws' is a shell function. Please remove or comment out the function in your shell profile (e.g., ~/.zshrc, ~/.bash_profile)."
  echo "[INFO] Function definition:"
  type aws
  exit 1
} || echo "[OK] No 'aws' function found."

# Check for aws in PATH
AWS_PATH=$(which aws || true)
if [ -z "$AWS_PATH" ]; then
  echo "[ERROR] AWS CLI not found in PATH. Please install AWS CLI v2."
  exit 1
else
  echo "[OK] AWS CLI found at $AWS_PATH"
fi

# Test AWS CLI basic command
echo "[INFO] Testing AWS CLI..."
if ! aws sts get-caller-identity; then
  echo "[ERROR] AWS CLI failed to run. Check your credentials and configuration."
  exit 1
else
  echo "[OK] AWS CLI is working."
fi

echo "[SUCCESS] AWS CLI environment is clean. You can now run AWS CLI commands without shell interference." 