#!/bin/sh
set -eu
base="${1:-http://127.0.0.1}"
curl --fail --silent --show-error --connect-timeout 3 --max-time 15 "$base/" | python3 -c 'import sys; assert "lang=\"it\"" in sys.stdin.read()'
curl --fail --silent --show-error --connect-timeout 3 --max-time 15 "$base/api/v1/system/status" | python3 -c 'import json,sys; assert json.load(sys.stdin)=={"product":"Enginia360","stage":"bootstrap","foundationDossierApproved":False,"businessCapabilitiesAvailable":False}'
for endpoint in live ready; do
  test "$(curl --fail --silent --show-error --connect-timeout 3 --max-time 15 "$base/health/$endpoint")" = Healthy
done
curl --fail --silent --show-error --connect-timeout 3 --max-time 15 "$base/openapi/v1.json" | python3 -c 'import json,sys; assert "/api/v1/system/status" in json.load(sys.stdin)["paths"]'
printf 'HTTP bootstrap smoke checks passed.\n'
