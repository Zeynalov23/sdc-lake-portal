#!/usr/bin/env bash
# Resolve AWS credentials on the host and write them where compose can read
# them.
#
# The containers deliberately do NOT mount ~/.aws. Profiles using SSO or
# credential_process need the AWS CLI to resolve, and the CLI is not in the
# image - nor should it be, since the cluster gets credentials a completely
# different way.
#
# This mirrors production more closely than a credentials file would: in EKS,
# Pod Identity injects short-lived credentials through the environment, and
# the application reads them without knowing where they came from. Same here,
# only the source differs.
set -euo pipefail

cd "$(dirname "$0")/.."

# 1. Credentials already exported in the shell. Nothing to resolve - the CLI
#    would only ignore them if we asked it about a named profile.
if [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  {
    echo "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}"
    echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}"
    [ -n "${AWS_SESSION_TOKEN:-}" ] && echo "AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}"
  } > .env.aws
  echo "Wrote .env.aws from the environment"

# 2. Otherwise ask the CLI to resolve whatever the profile does - SSO,
#    credential_process, a plain credentials file, an assumed role.
elif command -v aws >/dev/null 2>&1; then
  # Only pass --profile when one is actually set: passing it explicitly makes
  # the CLI resolve that profile and skip environment credentials entirely.
  PROFILE_ARGS=()
  [ -n "${AWS_PROFILE:-}" ] && PROFILE_ARGS=(--profile "${AWS_PROFILE}")

  if ! aws configure export-credentials "${PROFILE_ARGS[@]}" --format env-no-export > .env.aws 2>/dev/null; then
    rm -f .env.aws
    echo "Could not resolve AWS credentials." >&2
    echo "Check that 'aws sts get-caller-identity' works, and that the AWS" >&2
    echo "CLI is v2.13 or newer (aws --version) for export-credentials." >&2
    exit 1
  fi
  echo "Wrote .env.aws via the AWS CLI"

else
  echo "No AWS credentials in the environment and no aws CLI on PATH." >&2
  exit 1
fi

# Region is not part of the credentials, but the containers need it.
grep -q '^AWS_REGION=' .env.aws 2>/dev/null || \
  echo "AWS_REGION=${AWS_REGION:-eu-west-1}" >> .env.aws

echo "--- verifying ---"
aws sts get-caller-identity --query Arn --output text
