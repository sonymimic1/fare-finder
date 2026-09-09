#!/usr/bin/env bash
# Deploy one single-file Lambda from aws/<dir>/index.py (CLI mode; no flight-seed bridge needed).
# Usage: scripts/deploy-lambda.sh <function-name> <source-dir> [timeout-seconds] [ENV=VAL,...]
set -euo pipefail

FN="${1:?function name}"
SRC="${2:?source dir under aws/}"
TIMEOUT="${3:-10}"
ENVVARS="${4:-}"
REGION=us-east-1
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text --region "$REGION")"
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/flight-lambda-role"
BUILD="$(mktemp -d)"
ZIP="$BUILD/$FN.zip"

# EXTRA: space-separated files under aws/_shared to bundle alongside index.py (e.g. EXTRA="ecpay.py")
( cd "$ROOT/aws/$SRC" && zip -q -j "$ZIP" index.py )
for f in ${EXTRA:-}; do ( cd "$ROOT/aws/_shared" && zip -q -j "$ZIP" "$f" ); done
echo "zip: $(wc -c <"$ZIP") bytes, md5 $(md5 -q "$ZIP")"

if aws lambda get-function --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --zip-file "fileb://$ZIP" --region "$REGION" \
    --query '{fn:FunctionName,sha:CodeSha256,state:State}' --output json
  aws lambda wait function-updated --function-name "$FN" --region "$REGION"
  if [ -n "$ENVVARS" ]; then
    aws lambda update-function-configuration --function-name "$FN" --timeout "$TIMEOUT" \
      --environment "Variables={$ENVVARS}" --region "$REGION" --query '{fn:FunctionName,timeout:Timeout}' --output json
    aws lambda wait function-updated --function-name "$FN" --region "$REGION"
  fi
else
  if [ -n "$ENVVARS" ]; then
    aws lambda create-function --function-name "$FN" --runtime python3.12 --handler index.handler \
      --role "$ROLE_ARN" --timeout "$TIMEOUT" --zip-file "fileb://$ZIP" --environment "Variables={$ENVVARS}" --region "$REGION" \
      --query '{fn:FunctionName,sha:CodeSha256,state:State}' --output json
  else
    aws lambda create-function --function-name "$FN" --runtime python3.12 --handler index.handler \
      --role "$ROLE_ARN" --timeout "$TIMEOUT" --zip-file "fileb://$ZIP" --region "$REGION" \
      --query '{fn:FunctionName,sha:CodeSha256,state:State}' --output json
  fi
  aws lambda wait function-active --function-name "$FN" --region "$REGION"
fi
rm -rf "$BUILD"
echo "deployed $FN"
