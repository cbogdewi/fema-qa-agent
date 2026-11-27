#!/usr/bin/env bash
# Run once in AWS CloudShell (the >_ icon in the AWS console):
#   curl -fsSL https://raw.githubusercontent.com/cbogdewi/fema-qa-agent/main/infra/bootstrap.sh | bash
set -euo pipefail
REGION="us-east-2"   # must match AWS_REGION in .github/workflows/deploy.yml
STACK="fema-qa-agent-bootstrap"
TEMPLATE_URL="https://raw.githubusercontent.com/cbogdewi/fema-qa-agent/main/infra/bootstrap.yaml"

curl -fsSL "$TEMPLATE_URL" -o /tmp/bootstrap.yaml

# If this stack already exists, keep its choice (otherwise an update would delete the provider it owns).
CREATE_OIDC=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Parameters[?ParameterKey=='CreateOIDCProvider'].ParameterValue" --output text 2>/dev/null || true)
if [ "$CREATE_OIDC" != "true" ] && [ "$CREATE_OIDC" != "false" ]; then
  CREATE_OIDC=true
  if aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text \
       | grep -q "token.actions.githubusercontent.com"; then
    CREATE_OIDC=false
  fi
fi
# Never point at a provider that doesn't exist (an earlier update could have removed it).
if ! aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text \
     | grep -q "token.actions.githubusercontent.com"; then
  CREATE_OIDC=true
fi
echo "CreateOIDCProvider=$CREATE_OIDC"

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
