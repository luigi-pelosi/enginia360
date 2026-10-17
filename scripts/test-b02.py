#!/usr/bin/env python3
import json, sys, urllib.error, urllib.request


def request(url, token=None, method="GET", payload=None, extra_headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers, method=method),
            timeout=20,
        ) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, json.loads(body) if body else None


def login(base, user, password):
    status, body = request(
        base + "/api/v1/development/login",
        method="POST",
        payload={"username": user, "password": password},
    )
    assert status == 200, (status, body)
    return body["accessToken"]


def main():
    base = sys.argv[1]
    alpha = login(base, "operatore-alfa-sintetico", "synthetic-alpha-password")
    beta = login(base, "operatore-beta-sintetico", "synthetic-beta-password")
    outsider = login(base, "operatore-senza-membership", "synthetic-no-membership")
    no_read = login(base, "operatore-alfa-senza-lettura", "synthetic-no-read")
    status, ac = request(base + "/api/v1/organization/contexts", alpha)
    assert (
        status == 200
        and len(ac) == 2
        and {x["tenantId"] for x in ac} == {"11111111-1111-1111-1111-111111111111"}
        and {x["capabilityEnabled"] for x in ac} == {True, False}
    )
    status, bc = request(base + "/api/v1/organization/contexts", beta)
    assert status == 200 and len(bc) == 1 and bc[0]["tenantId"].startswith("2222")
    assert request(base + "/api/v1/organization/contexts", outsider) == (200, [])
    allowed = {
        "tenantId": "11111111-1111-1111-1111-111111111111",
        "legalEntityId": "11111111-1111-1111-1111-111111111101",
        "siteId": "11111111-1111-1111-1111-111111110101",
        "warehouseId": "11111111-1111-1111-1111-111111100101",
        "message": "  Nota sintetica persistita  ",
    }
    status, note = request(
        base + "/api/v1/organization/context-notes", alpha, "POST", allowed
    )
    assert status == 201 and note["message"] == "Nota sintetica persistita", (
        status,
        note,
    )
    assert request(
        base + f"/api/v1/organization/context-notes/{note['id']}", alpha
    ) == (200, note)
    assert (
        request(base + f"/api/v1/organization/context-notes/{note['id']}", beta)[0]
        == 404
    )
    status, denied = request(
        base + f"/api/v1/organization/context-notes/{note['id']}", no_read
    )
    assert status == 404, (
        "same-tenant identity without read scope must receive 404",
        status,
        denied,
    )
    assert (
        request(base + f"/api/v1/organization/context-notes/{note['id']}", outsider)[0]
        == 404
    )
    assert (
        request(
            base + f"/api/v1/organization/context-notes/{note['id']}",
            no_read,
            extra_headers={
                "X-User-Id": "aaaaaaaa-0000-0000-0000-000000000001",
                "X-Tenant-Id": allowed["tenantId"],
            },
        )[0]
        == 404
    )
    assert request(base + "/api/v1/organization/contexts", no_read) == (200, [])
    assert (
        request(
            base
            + "/api/v1/organization/context-notes/11111111-0000-0000-0000-000000000001",
            alpha,
        )[0]
        == 200
    )
    assert (
        request(
            base
            + "/api/v1/organization/context-notes/11111111-0000-0000-0000-000000000001",
            no_read,
        )[0]
        == 404
    )
    assert (
        request(
            base
            + "/api/v1/organization/context-notes/11111111-0000-0000-0000-000000000002",
            alpha,
        )[0]
        == 404
    )
    for invalid in ["", "   ", "x" * 201]:
        assert (
            request(
                base + "/api/v1/organization/context-notes",
                alpha,
                "POST",
                allowed | {"message": invalid},
            )[0]
            == 400
        )
    mixed = allowed | {"legalEntityId": "11111111-1111-1111-1111-111111111102"}
    assert (
        request(base + "/api/v1/organization/context-notes", alpha, "POST", mixed)[0]
        == 403
    )
    cross = allowed | {
        "tenantId": "22222222-2222-2222-2222-222222222222",
        "legalEntityId": "22222222-2222-2222-2222-222222222201",
        "siteId": "22222222-2222-2222-2222-222222220101",
        "warehouseId": "22222222-2222-2222-2222-222222220101",
    }
    assert (
        request(base + "/api/v1/organization/context-notes", alpha, "POST", cross)[0]
        == 403
    )
    disabled = allowed | {
        "legalEntityId": "11111111-1111-1111-1111-111111111102",
        "siteId": "11111111-1111-1111-1111-111111110201",
        "warehouseId": "11111111-1111-1111-1111-111111100301",
    }
    status, problem = request(
        base + "/api/v1/organization/context-notes", alpha, "POST", disabled
    )
    assert status == 403 and problem["title"] == "Capability disabled"
    pids = []
    for token, subject in [
        (alpha, "aaaaaaaa-0000-0000-0000-000000000001"),
        (beta, "bbbbbbbb-0000-0000-0000-000000000001"),
    ] * 5:
        status, session = request(base + "/api/v1/organization/database-session", token)
        assert status == 200 and session["identitySubject"] == subject
        pids.append(session["backendPid"])
    assert len(set(pids)) == 1, pids
    bad = alpha[:-1] + ("A" if alpha[-1] != "A" else "B")
    assert request(base + "/api/v1/organization/contexts", bad)[0] == 401
    print(
        "PASS: backend login, authorized contexts, note durability/isolation, validation, tampering, disabled visibility, JWT signature rejection, and one-PID pooled isolation."
    )


if __name__ == "__main__":
    main()
