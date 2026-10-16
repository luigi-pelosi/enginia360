#!/usr/bin/env python3
"""Exercise the isolated B01 Keycloak proof through its HTTPS endpoints."""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("KEYCLOAK_URL", "https://keycloak:8443").rstrip("/")
CA_FILE = os.environ.get("KEYCLOAK_CA_FILE", "/run/secrets/keycloak-ca.crt")
ADMIN_USERNAME = os.environ["KEYCLOAK_ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]
TEST_USERNAME = os.environ["KEYCLOAK_TEST_USERNAME"]
TEST_PASSWORD = os.environ["KEYCLOAK_TEST_PASSWORD"]
REALM = "enginia360-proof"
CLIENT_ID = "enginia360-proof-client"
CONTEXT = ssl.create_default_context(cafile=CA_FILE)


def request(path: str, *, method: str = "GET", token: str | None = None,
            form: dict[str, str] | None = None, payload: object | None = None,
            expected: tuple[int, ...] = (200,)) -> tuple[int, object | None]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode()
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=CONTEXT, timeout=10) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    if status not in expected:
        raise AssertionError(f"{method} {path}: expected {expected}, received {status}")
    if not body:
        return status, None
    return status, json.loads(body)


def token(realm: str, form: dict[str, str]) -> dict[str, object]:
    _, body = request(f"/realms/{realm}/protocol/openid-connect/token", method="POST", form=form)
    assert isinstance(body, dict)
    return body


def jwt_claims(encoded_token: str) -> dict[str, object]:
    parts = encoded_token.split(".")
    if len(parts) != 3:
        raise AssertionError("Access token is not a compact JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    if not isinstance(claims, dict):
        raise AssertionError("JWT payload is not an object")
    return claims


def admin_token() -> str:
    result = token("master", {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    return str(result["access_token"])


def configure_realm(admin: str) -> str:
    request("/admin/realms", method="POST", token=admin, payload={
        "realm": REALM,
        "enabled": True,
        "sslRequired": "all",
        "accessTokenLifespan": 300,
        "revokeRefreshToken": True,
    }, expected=(201, 409))
    _, clients = request(f"/admin/realms/{REALM}/clients", token=admin)
    assert isinstance(clients, list)
    existing = next((item for item in clients if item.get("clientId") == CLIENT_ID), None)
    if existing is None:
        request(f"/admin/realms/{REALM}/clients", method="POST", token=admin, payload={
            "clientId": CLIENT_ID,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "secret": CLIENT_SECRET,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": False,
            "fullScopeAllowed": False,
            "protocolMappers": [{
                "name": "proof-client-audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.client.audience": CLIENT_ID,
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                    "introspection.token.claim": "true",
                },
            }],
        }, expected=(201,))
    _, users = request(f"/admin/realms/{REALM}/users?username={urllib.parse.quote(TEST_USERNAME)}", token=admin)
    assert isinstance(users, list)
    if users:
        user_id = str(users[0]["id"])
    else:
        request(f"/admin/realms/{REALM}/users", method="POST", token=admin, payload={
            "username": TEST_USERNAME,
            "enabled": True,
            "email": f"{TEST_USERNAME}@example.invalid",
            "emailVerified": True,
            "firstName": "Synthetic",
            "lastName": "User",
            "requiredActions": [],
            "credentials": [{"type": "password", "value": TEST_PASSWORD, "temporary": False}],
        }, expected=(201,))
        _, users = request(f"/admin/realms/{REALM}/users?username={urllib.parse.quote(TEST_USERNAME)}", token=admin)
        assert isinstance(users, list) and len(users) == 1
        user_id = str(users[0]["id"])
    return user_id


def main() -> None:
    admin = admin_token()
    user_id = configure_realm(admin)
    request(f"/realms/{REALM}/protocol/openid-connect/userinfo", expected=(401,))

    issued = token(REALM, {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "scope": "openid",
    })
    access_token = str(issued["access_token"])
    refresh_token = str(issued["refresh_token"])

    _, profile = request(f"/realms/{REALM}/protocol/openid-connect/userinfo", token=access_token)
    assert isinstance(profile, dict) and profile.get("preferred_username") == TEST_USERNAME
    _, introspection = request(f"/realms/{REALM}/protocol/openid-connect/token/introspect", method="POST", form={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "token": access_token,
    })
    assert isinstance(introspection, dict) and introspection.get("active") is True
    _, sessions = request(f"/admin/realms/{REALM}/users/{user_id}/sessions", token=admin)
    assert isinstance(sessions, list)
    claims = jwt_claims(access_token)
    session_id = str(claims.get("sid") or claims.get("session_state") or "")
    matching_session = next((session for session in sessions if session.get("id") == session_id), None)
    assert matching_session is not None, "Issued token does not match a server-side user session"
    session_clients = matching_session.get("clients")
    assert isinstance(session_clients, dict) and CLIENT_ID in session_clients.values(), \
        "Issued token session is not associated with the proof client"

    request(f"/realms/{REALM}/protocol/openid-connect/logout", method="POST", form={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "refresh_token": refresh_token,
    }, expected=(204,))
    for _ in range(10):
        _, introspection = request(f"/realms/{REALM}/protocol/openid-connect/token/introspect", method="POST", form={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "token": access_token,
        })
        if isinstance(introspection, dict) and introspection.get("active") is False:
            break
        time.sleep(0.5)
    else:
        raise AssertionError("Access token remained active after session logout")
    request(f"/realms/{REALM}/protocol/openid-connect/userinfo", token=access_token, expected=(401,))
    print("PASS: HTTPS authentication, anonymous rejection, session validation, and logout revocation verified.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
