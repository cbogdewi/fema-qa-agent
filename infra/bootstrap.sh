#!/usr/bin/env bash
# Run once in AWS CloudShell (the >_ icon in the AWS console):
#   curl -fsSL https://raw.githubusercontent.com/cbogdewi/fema-qa-agent/main/infra/bootstrap.sh | bash
set -euo pipefail
REGION="us-east-2"   # must match AWS_REGION in .github/workflows/deploy.yml
STACK="fema-qa-agent-bootstrap"
TEMPLATE_URL="https://raw.githubusercontent.com/cbogdewi/fema-qa-agent/main/infra/bootstrap.yaml"

curl -fsSL "$TEMPLATE_URL" -o /tmp/bootstrap.yaml

CREATE_OIDC=true
if aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text \
     | grep -q "token.actions.githubusercontent.com"; then
  CREATE_OIDC=false
fi

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file /tmp/bootstrap.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides CreateOIDCProvider="$CREATE_OIDC"

ROLE_ARN=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='DeployRoleArn'].OutputValue" --output text)

echo
echo "Done. Add this as a GitHub repository VARIABLE named AWS_ROLE_ARN:"
echo
echo "    $ROLE_ARN"
echo
