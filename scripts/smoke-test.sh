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
# -f alone is not enough: it treats a 3xx as success, so a TemporaryRedirect
# from S3 looks like a working upload. Check the status code explicitly.
for attempt in 1 2 3 4 5; do
  code=$(echo "hello from the smoke test" | curl -s -o /tmp/upload-out -w '%{http_code}' \
    -X PUT --data-binary @- -H "Content-Type: text/plain" "${url}")
  if [ "${code}" = "200" ]; then
    echo "    uploaded"
    break
  fi
  echo "    attempt ${attempt}: HTTP ${code}"
  cat /tmp/upload-out
  if [ "${attempt}" = "5" ]; then echo "--> upload failed"; exit 1; fi
  sleep 3
done

echo "--> listing"
listing=$(curl -sf "${API}/spaces/${SPACE_ID}/files" -H "X-Dev-User: ${USER_ID}")
echo "${listing}"
count=$(echo "${listing}" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])")
if [ "${count}" -lt 1 ]; then
  echo "--> the upload did not land: listing is empty"
  exit 1
fi

echo "--> a stranger must be denied"
code=$(curl -s -o /dev/null -w '%{http_code}' \
  "${API}/spaces/${SPACE_ID}/files" -H "X-Dev-User: mallory")
if [ "${code}" = "403" ]; then
  echo "    mallory got 403"
else
  echo "    expected 403, got ${code}"; exit 1
fi

echo "--> adding a consumer"
curl -sf -X POST "${API}/spaces/${SPACE_ID}/members" \
  -H "Content-Type: application/json" -H "X-Dev-User: ${USER_ID}" \
  -d '{"email":"dave@example.com","role":"CONSUMER"}' > /dev/null
echo "    dave added"

echo "--> the consumer can read but not write"
code=$(curl -s -o /dev/null -w '%{http_code}' \
  "${API}/spaces/${SPACE_ID}/files" -H "X-Dev-User: dev-dave")
[ "${code}" = "200" ] || { echo "    expected 200 reading, got ${code}"; exit 1; }

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  "${API}/spaces/${SPACE_ID}/files/upload" \
  -H "Content-Type: application/json" -H "X-Dev-User: dev-dave" \
  -d '{"key":"sales/nope.txt","content_type":"text/plain"}')
[ "${code}" = "403" ] || { echo "    consumer could write: got ${code}"; exit 1; }
echo "    read 200, write 403"

echo "--> the consumer cannot manage members"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  "${API}/spaces/${SPACE_ID}/members" \
  -H "Content-Type: application/json" -H "X-Dev-User: dev-dave" \
  -d '{"email":"eve@example.com","role":"CONSUMER"}')
[ "${code}" = "403" ] || { echo "    consumer managed members: got ${code}"; exit 1; }
echo "    403"

echo "--> deputy assignment is limited to one"
curl -sf -X PUT "${API}/spaces/${SPACE_ID}/deputy" \
  -H "Content-Type: application/json" -H "X-Dev-User: ${USER_ID}" \
  -d '{"email":"bob@example.com"}' > /dev/null
code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT \
  "${API}/spaces/${SPACE_ID}/deputy" \
  -H "Content-Type: application/json" -H "X-Dev-User: ${USER_ID}" \
  -d '{"email":"carol@example.com"}')
[ "${code}" = "409" ] || { echo "    second deputy accepted: got ${code}"; exit 1; }
echo "    second deputy rejected with 409"

echo "--> the deputy has admin rights"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  "${API}/spaces/${SPACE_ID}/members" \
  -H "Content-Type: application/json" -H "X-Dev-User: dev-bob" \
  -d '{"email":"frank@example.com","role":"PRODUCER"}')
[ "${code}" = "201" ] || { echo "    deputy could not add a member: got ${code}"; exit 1; }
echo "    deputy added a member"

echo "--> the owner cannot be removed"
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE \
  "${API}/spaces/${SPACE_ID}/members/${USER_ID}" -H "X-Dev-User: ${USER_ID}")
[ "${code}" = "409" ] || { echo "    owner was removable: got ${code}"; exit 1; }
echo "    409"

echo "--> all checks passed"
