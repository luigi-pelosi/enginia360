#!/bin/sh
set -eu

COMPOSE_FILE="compose.keycloak-proof.yaml"
PROJECT_NAME="enginia360-keycloak-proof-$(openssl rand -hex 6)"
RUNTIME_DIR="$(mktemp -d "${TMPDIR:-/tmp}/enginia360-keycloak-proof.XXXXXX")"
export KEYCLOAK_CERT_DIR="$RUNTIME_DIR"
export KEYCLOAK_ADMIN_USERNAME="proof-admin-$(openssl rand -hex 8)"
export KEYCLOAK_ADMIN_PASSWORD="$(openssl rand -base64 36 | tr -d '\n')"
export KEYCLOAK_CLIENT_SECRET="$(openssl rand -base64 36 | tr -d '\n')"
export KEYCLOAK_TEST_USERNAME="proof-user-$(openssl rand -hex 8)"
export KEYCLOAK_TEST_PASSWORD="$(openssl rand -base64 36 | tr -d '\n')"

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs --tail=100 keycloak >&2 || true
  fi
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$RUNTIME_DIR"
  remaining="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT_NAME")"
  [ -z "$remaining" ] || { echo "FAIL: proof containers remain after cleanup" >&2; exit 1; }
  remaining_networks="$(docker network ls --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.ID}}')"
  [ -z "$remaining_networks" ] || { echo "FAIL: proof networks remain after cleanup" >&2; exit 1; }
  return "$status"
}
trap cleanup EXIT INT TERM

openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 1 \
  -subj "/CN=keycloak" -addext "subjectAltName=DNS:keycloak" \
  -keyout "$RUNTIME_DIR/keycloak.key" -out "$RUNTIME_DIR/keycloak.crt" >/dev/null 2>&1
chmod 600 "$RUNTIME_DIR/keycloak.key"
chown 1000:1000 "$RUNTIME_DIR/keycloak.key" "$RUNTIME_DIR/keycloak.crt"

docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build --wait --wait-timeout 180
NETWORK_ID="$(docker network ls --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.ID}}' | head -n 1)"
[ -n "$NETWORK_ID" ] || { echo "FAIL: proof network not found" >&2; exit 1; }

docker run --rm \
  --network "$NETWORK_ID" \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 128m --cpus 0.5 --pids-limit 64 \
  --tmpfs /tmp:rw,noexec,nosuid,size=8m \
  -e KEYCLOAK_URL=https://keycloak:8443 \
  -e KEYCLOAK_CA_FILE=/run/secrets/keycloak-ca.crt \
  -e KEYCLOAK_ADMIN_USERNAME -e KEYCLOAK_ADMIN_PASSWORD \
  -e KEYCLOAK_CLIENT_SECRET -e KEYCLOAK_TEST_USERNAME -e KEYCLOAK_TEST_PASSWORD \
  -v "$PWD/scripts/test-keycloak-proof.py:/proof/test.py:ro" \
  -v "$RUNTIME_DIR/keycloak.crt:/run/secrets/keycloak-ca.crt:ro" \
  python:3.14.3-alpine3.23@sha256:faee120f7885a06fcc9677922331391fa690d911c020abb9e8025ff3d908e510 \
  python /proof/test.py

CONTAINER_ID="$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps -q keycloak)"
docker inspect "$CONTAINER_ID" --format 'Keycloak security: user={{.Config.User}} readonly={{.HostConfig.ReadonlyRootfs}} capdrop={{json .HostConfig.CapDrop}} no-new-privileges={{json .HostConfig.SecurityOpt}} ports={{json .HostConfig.PortBindings}}'
docker stats --no-stream --format 'Keycloak resources: memory={{.MemUsage}} cpu={{.CPUPerc}} pids={{.PIDs}}' "$CONTAINER_ID"
echo "PASS: isolated Keycloak proof completed; cleanup follows."
