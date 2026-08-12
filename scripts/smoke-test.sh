#!/usr/bin/env bash
# End-to-end check of the create-space flow against real AWS.
#
# Proves the whole chain: the API writes to DynamoDB, the stream reaches the
# EventBridge Pipe, the pipe fills SQS, the provisioning service consumes it,
# creates the bucket and flips status to READY.
set -euo pipefail

API="${API:-http://localhost:8000}"
USER_ID="${USER_ID:-alice}"
SPACE_ID="${SPACE_ID:-smoke-$(date +%s)}"

echo "--> creating space ${SPACE_ID}"
curl -sf -X POST "${API}/spaces" \
  -H "Content-Type: application/json" \
  -H "X-Dev-User: ${USER_ID}" \
  -d "{\"spaceId\":\"${SPACE_ID}\",\"tier\":\"standard\"}"
echo

echo "--> waiting for provisioning (up to 90s)"
for i in $(seq 1 30); do
  status=$(curl -sf "${API}/spaces/${SPACE_ID}" -H "X-Dev-User: ${USER_ID}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status'))")
  echo "    [${i}] status=${status}"
  if [ "${status}" = "READY" ]; then echo "--> READY"; break; fi
  if [ "${status}" = "FAILED" ]; then
    echo "--> FAILED - check provisioning-service logs"; exit 1
  fi
  if [ "${i}" = "30" ]; then echo "--> timed out, still PENDING"; exit 1; fi
  sleep 3
done

echo "--> requesting an upload URL"
url=$(curl -sf -X POST "${API}/spaces/${SPACE_ID}/files/upload" \
  -H "Content-Type: application/json" -H "X-Dev-User: ${USER_ID}" \
  -d '{"key":"sales/hello.txt","content_type":"text/plain"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")

echo "--> uploading"
echo "hello from the smoke test" | curl -sf -X PUT --data-binary @- \
  -H "Content-Type: text/plain" "${url}"

echo "--> listing"
curl -sf "${API}/spaces/${SPACE_ID}/files" -H "X-Dev-User: ${USER_ID}"
echo

echo "--> a stranger must be denied"
code=$(curl -s -o /dev/null -w '%{http_code}' \
  "${API}/spaces/${SPACE_ID}/files" -H "X-Dev-User: mallory")
if [ "${code}" = "403" ]; then
  echo "    mallory got 403"
else
  echo "    expected 403, got ${code}"; exit 1
fi

echo "--> all checks passed"
