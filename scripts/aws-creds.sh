#!/usr/bin/env bash
# Resolve AWS credentials on the host and write them where compose can read
# them.
#
# The containers deliberately do NOT mount ~/.aws. Profiles that use SSO or
# credential_process need the AWS CLI to resolve, and the CLI is not in the
# image - nor should it be, since the cluster gets credentials a completely
# different way.
#
# This mirrors production more closely than a credentials file would: in EKS,
# Pod Identity injects short-lived credentials through the environment, and
# the application code reads them without knowing where they came from. Same
# here, just a different source.
#
# Credentials are temporary. Re-run this when calls start failing with
# ExpiredToken, then restart compose.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found on the host - needed to resolve your profile" >&2
  exit 1
fi

PROFILE="${AWS_PROFILE:-default}"

if ! aws configure export-credentials --profile "$PROFILE" >/dev/null 2>&1; then
  echo "Could not resolve credentials for profile '$PROFILE'." >&2
  echo "If you use SSO, run: aws sso login --profile $PROFILE" >&2
  exit 1
fi

aws configure export-credentials --profile "$PROFILE" --format env-no-export > .env.aws

echo "Wrote .env.aws for profile '$PROFILE'"
aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text
