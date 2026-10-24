#!/usr/bin/env python3
"""Guarded R04.a acceptance, reusing actual R03.a2/R00 TLS fixtures and cleanup."""

import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import tempfile
import time
import uuid
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "r03a2", ROOT / "scripts/run-r03a2-tests.py"
)
r03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r03)
r00 = r03.r00
r00.CONFIG = ROOT / "compose.r04a-test.yaml"
run = r00.run


def main():
    if not os.environ.get("TMPDIR"):
        raise ValueError("private TMPDIR required")
    pool = os.environ.get("R04A_POOL_SIZE", "4")
    if pool not in ("1", "4"):
        raise ValueError("pool must be 1 or 4")
    os.environ["R03A2_POOL_SIZE"] = pool
    project = "enginia360-r00b-" + secrets.token_hex(6)
    before_volumes = r00.inventory("volume")
    before_running = set(run(["docker", "ps", "-q", "--no-trunc"]).splitlines())
    with tempfile.TemporaryDirectory(
        prefix=project + "-", dir=os.environ["TMPDIR"]
    ) as directory:
        state = Path(directory)
        values = {
            k: secrets.token_hex(24)
            for k in (
                "R00_INFRA_PASSWORD",
                "R00_OWNER_PASSWORD",
                "R00_APP_PASSWORD",
                "R00_CLIENT_SECRET",
            )
        }
        values.update(R00_STATE=str(state), R00_POOL_SIZE=pool)
        envfile = state / "runtime.env"
        envfile.write_text("".join(k + "=" + v + "\n" for k, v in values.items()))
        envfile.chmod(0o600)
        run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=Ephemeral R04 CA",
                "-addext",
                "basicConstraints=critical,CA:TRUE",
                "-keyout",
                str(state / "ca.key"),
                "-out",
                str(state / "ca.crt"),
            ]
        )
        (state / "ca.key").chmod(0o600)
        (state / "public").mkdir()
        (state / "public/ca.crt").write_bytes((state / "ca.crt").read_bytes())
        for service, host, uid in [
            ("postgres", "postgres", 70),
            ("api", "api.r00.test", 1654),
            ("web", "app.r00.test", 101),
            ("identity", "idp.r00.test", 1000),
        ]:
            r00.certificate(state, service, host, uid)
        (state / "postgres/pg_hba.conf").write_text(
            "local all all trust\nhostnossl all all all reject\nhostssl all all all scram-sha-256\n"
        )
        sql = r03.fixtures(state, values["R00_CLIENT_SECRET"], stock_setup=False)
        fixture = json.loads((state / "browser.json").read_text())
        ctx = fixture["contexts"][0]
        data = fixture["workshop"][0]
        sql += f'\nUPDATE inventory.stock SET "Physical"=2 WHERE "TenantId"=\'{ctx["tenantId"]}\' AND "CatalogItemId"=\'{data["partId"]}\';'
        sql += f"\nINSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.reservations.read','{ctx['siteId']}','{ctx['warehouseId']}');"
        ext = fixture["contexts"][1]
        extdata = fixture["workshop"][1]
        sql += f"\nINSERT INTO organization_access.capability_activations VALUES ('{ext['legalEntityId']}','inventory',true); INSERT INTO inventory.stock VALUES ('{ext['tenantId']}','{ext['legalEntityId']}','{ext['siteId']}','{ext['warehouseId']}','{extdata['partId']}',2); INSERT INTO inventory.picking_policies VALUES ('{ext['tenantId']}','{ext['legalEntityId']}',1,false); INSERT INTO inventory.picking_locations VALUES ('{ext['tenantId']}','{ext['legalEntityId']}','{ext['siteId']}','{ext['warehouseId']}','External origin',NULL); INSERT INTO workshop.carcass_policies VALUES ('{ext['tenantId']}','{ext['legalEntityId']}','{extdata['documentTypeId']}','{extdata['partId']}',1,true); INSERT INTO inventory.carcass_locations VALUES ('{ext['tenantId']}','{ext['legalEntityId']}','{ext['siteId']}','{ext['warehouseId']}',1,'External carcass');"
        for action in (
            "reservations.read",
            "reservations.create",
            "picks.read",
            "picks.create",
            "consumptions.read",
            "consumptions.create",
            "carcass-returns.read",
            "carcass-returns.create",
        ):
            sql += f"\nINSERT INTO organization_access.company_permissions SELECT '{uuid.uuid4()}',m.\"Id\",'{ext['tenantId']}','{ext['legalEntityId']}','inventory.{action}','{ext['siteId']}','{ext['warehouseId']}' FROM organization_access.memberships m WHERE m.\"TenantId\"='{ext['tenantId']}';"
        second = next(
            c["warehouseId"]
            for c in fixture["deniedContexts"]
            if c["legalEntityId"] == ctx["legalEntityId"]
            and c["siteId"] == ctx["siteId"]
        )
        sql += f"\nINSERT INTO inventory.stock VALUES ('{ctx['tenantId']}','{ctx['legalEntityId']}','{ctx['siteId']}','{second}','{data['partId']}',2);"
        for action in ("reservations.read", "reservations.create"):
            sql += f"\nINSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.{action}','{ctx['siteId']}','{second}');"
        (state / "control").mkdir()
        (state / "control").chmod(0o777)
        command = [
            "docker",
            "compose",
            "--env-file",
            str(envfile),
            "-p",
            project,
            "-f",
            str(ROOT / "compose.r04a-test.yaml"),
        ]

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        previous = {
            s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)
        }
        holders = []
        try:
            run(command + ["build"], timeout=480)
            run(
                command
                + [
                    "up",
                    "-d",
                    "--wait",
                    "--wait-timeout",
                    "180",
                    "postgres",
                    "identity",
                ],
                timeout=210,
            )
            run(command + ["run", "--rm", "--no-deps", "-T", "migrator"], timeout=90)
            query = command + [
                "exec",
                "-T",
                "postgres",
                "psql",
                "-X",
                "-qAt",
                "-U",
                "postgres",
                "-d",
                "runtime",
                "-v",
                "ON_ERROR_STOP=1",
            ]
            assert (
                run(query + ["-c", "SELECT count(*) FROM workshop.orders"]).strip()
                == "0"
            )
            run(query, input=sql)
            run(command + ["up", "-d", "api", "web"], timeout=120)
            browser = subprocess.Popen(
                command + ["run", "--rm", "--no-deps", "-T", "browser"], cwd=ROOT
            )
            try:
                deadline = time.monotonic() + 240
                while browser.poll() is None:
                    if time.monotonic() > deadline:
                        raise TimeoutError("R04 browser deadline")
                    request = state / "control/request"
                    if request.exists():
                        action = request.read_text()
                        request.unlink()
                        if action == "consume-fault-on":
                            run(
                                query,
                                input="CREATE FUNCTION inventory.synthetic_consume_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic bounded consumption fault'; END $$; CREATE TRIGGER synthetic_consume_fault BEFORE INSERT ON inventory.consumptions FOR EACH ROW EXECUTE FUNCTION inventory.synthetic_consume_fault();",
                            )
                        elif action == "consume-fault-off":
                            run(
                                query,
                                input="DROP TRIGGER synthetic_consume_fault ON inventory.consumptions; DROP FUNCTION inventory.synthetic_consume_fault();",
                            )
                        elif action == "stock-profile-local":
                            profile = {
                                k: str(uuid.uuid4())
                                for k in (
                                    "commandId",
                                    "verificationReference",
                                    "sourceId",
                                    "profileId",
                                )
                            }
                            profile.update(
                                tenantId=ctx["tenantId"],
                                legalEntityId=ctx["legalEntityId"],
                                actorMembershipId=fixture["adminMembershipId"],
                                domain="stock",
                                direction="Enginia360ToExternal",
                                expectedVersion=0,
                            )
                            (state / "public/stock-profile.json").write_text(
                                json.dumps(profile)
                            )
                            (state / "public/stock-profile.json").chmod(0o444)
                            owner = command + [
                                "run",
                                "--rm",
                                "--no-deps",
                                "-T",
                                "-v",
                                str(ROOT / "scripts/owner-stock-profile.py")
                                + ":/proof/stock.py:ro",
                                "--entrypoint",
                                "python3",
                                "migrator",
                                "/proof/stock.py",
                                "/run/tls/stock-profile.json",
                            ]
                            for _ in range(2):
                                assert "exact immutable history read back" in run(
                                    owner, timeout=30
                                )
                            print(
                                "PASS R04A actual CA-verified owner CLI initial stock setup and immutable exact replay",
                                flush=True,
                            )
                        elif action.startswith("external-history:"):
                            order, line, group, reservation, pick, installation = [
                                str(uuid.UUID(v)) for v in action.split(":")[1:]
                            ]
                            t, c, s, w = [
                                ext[k]
                                for k in (
                                    "tenantId",
                                    "legalEntityId",
                                    "siteId",
                                    "warehouseId",
                                )
                            ]
                            part = extdata["partId"]
                            doc = extdata["documentTypeId"]
                            # Synthetic pre-migration history, owned by controller only. App never reads foreign private SQL.
                            run(
                                query,
                                input=f"""INSERT INTO inventory.reservations VALUES ('{reservation}','{t}','{order}','{line}','{c}','{s}','{w}','{part}',8,1,'{group}');
INSERT INTO inventory.picks VALUES ('{pick}','{t}','{reservation}','{order}','{group}','{line}','{c}','{s}','{w}','{part}',8,0.5,1,'External origin',NULL,'{pick}',clock_timestamp(),'{uuid.uuid4()}');
INSERT INTO workshop.installations VALUES ('{installation}','{t}','{pick}','{reservation}','{order}','{group}','{line}','{c}','{s}','{w}','{part}',8,0.25,1,'{doc}',7,clock_timestamp(),'{uuid.uuid4()}',1,true);
""",
                            )
                            legacy_local = run(
                                query,
                                input=f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}',(SELECT \"Id\" FROM organization_access.memberships WHERE \"TenantId\"='{t}'),'{uuid.uuid4()}','Enginia360ToExternal','{uuid.uuid4()}','{uuid.uuid4()}'); ROLLBACK;",
                            )
                            assert "original_stock_profile_missing" in legacy_local, (
                                "local setup must not retroactively authorize uncaptured historical material facts"
                            )
                            run(
                                query,
                                input=f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}',(SELECT \"Id\" FROM organization_access.memberships WHERE \"TenantId\"='{t}'),'{uuid.uuid4()}','ExternalToEnginia360','{uuid.uuid4()}','{uuid.uuid4()}'); COMMIT;",
                            )
                        elif action == "race-stock":
                            run(
                                query,
                                input=f"""UPDATE inventory.stock SET "Physical"=2+(SELECT coalesce(sum("Quantity"),0) FROM inventory.reservations WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}')-(SELECT coalesce(sum("Quantity"),0) FROM inventory.consumptions WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}') WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}' AND "CatalogItemId"='{data["partId"]}';""",
                            )
                        elif action == "catalog-next":
                            run(
                                query,
                                input=f'UPDATE catalog.items SET "Version"=9 WHERE "TenantId"=\'{ctx["tenantId"]}\' AND "Id"=\'{data["partId"]}\';',
                            )
                        elif action in ("capability-off", "capability-on"):
                            run(
                                query,
                                input=f'UPDATE organization_access.capability_activations SET "Enabled"={"true" if action.endswith("-on") else "false"} WHERE "LegalEntityId"=\'{ctx["legalEntityId"]}\' AND "Capability"=\'inventory\';',
                            )
                        elif action in ("database-outage", "database-recover"):
                            run(
                                command
                                + [
                                    "pause"
                                    if action == "database-outage"
                                    else "unpause",
                                    "postgres",
                                ],
                                timeout=30,
                            )
                        elif action == "binding-revoke":
                            run(
                                query,
                                input=f'DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"=(SELECT "IdentitySubject"::uuid FROM organization_access.memberships WHERE "Id"=\'{fixture["adminMembershipId"]}\');',
                            )
                        elif action in (
                            "picking-off",
                            "picking-missing",
                            "picking-restore",
                        ):
                            if action == "picking-off":
                                statement = f'UPDATE inventory.picking_policies SET "PreparationEnabled"=false,"Version"=2 WHERE "TenantId"=\'{ctx["tenantId"]}\' AND "LegalEntityId"=\'{ctx["legalEntityId"]}\';'
                            elif action == "picking-missing":
                                statement = f"DELETE FROM inventory.picking_policies WHERE \"TenantId\"='{ctx['tenantId']}' AND \"LegalEntityId\"='{ctx['legalEntityId']}';"
                            else:
                                statement = f"INSERT INTO inventory.picking_policies VALUES ('{ctx['tenantId']}','{ctx['legalEntityId']}',3,true);"
                            run(query, input=statement)
                        elif action.startswith("target-stock:"):
                            scope = action.split(":")[1]
                            if scope not in (
                                "read",
                                "common",
                                "site",
                                "warehouse",
                                "exact",
                                "revoke",
                            ):
                                raise ValueError("unknown synthetic scope")
                            target = fixture["grantTargetMembershipId"]
                            t, c, s, w = [
                                ctx[k]
                                for k in (
                                    "tenantId",
                                    "legalEntityId",
                                    "siteId",
                                    "warehouseId",
                                )
                            ]
                            grant = f"DELETE FROM organization_access.company_permissions WHERE \"MembershipId\"='{target}' AND \"Permission\" LIKE 'inventory.%';"
                            grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.reservations.read','{s}','{w}');"
                            if scope in ("site", "warehouse", "exact"):
                                site = "NULL" if scope == "warehouse" else "'" + s + "'"
                                warehouse = "NULL" if scope == "site" else "'" + w + "'"
                                grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.reservations.create',{site},{warehouse});"
                            if scope == "common":
                                grant += f"INSERT INTO organization_access.common_edit_permissions VALUES ('{target}','{t}') ON CONFLICT DO NOTHING;"
                            run(query, input=grant)
                        elif action == "hold-stock" or action.startswith("hold-line:"):
                            holder = subprocess.Popen(
                                query + ["-f", "-"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                text=True,
                            )
                            holders.append(holder)
                            if action == "hold-stock":
                                lock = f"""BEGIN; SELECT "Physical" FROM inventory.stock WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}' AND "CatalogItemId"='{data["partId"]}' FOR UPDATE;"""
                            else:
                                line = str(uuid.UUID(action.split(":")[1]))
                                lock = f"BEGIN; SELECT pg_advisory_lock(hashtextextended('inventory:line:{ctx['tenantId']}:{line}',0));"
                            holder.stdin.write(
                                lock + "\nSELECT pg_backend_pid();\n\\echo LOCKED\n"
                            )
                            holder.stdin.flush()
                            output = r03.marker(holder, b"LOCKED")
                            holder_pid = int(
                                [v for v in output.splitlines() if v.isdigit()][-1]
                            )
                        elif action.startswith("wait-lock:"):
                            required = int(action.split(":")[1])
                            deadline_lock = time.monotonic() + 10
                            while True:
                                count = int(
                                    run(
                                        query
                                        + [
                                            "-c",
                                            f"WITH RECURSIVE chain(pid,blocker) AS (SELECT pid,unnest(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE usename='runtime_app' UNION SELECT chain.pid,unnest(pg_blocking_pids(chain.blocker)) FROM chain) SELECT count(DISTINCT pid) FROM chain WHERE blocker={holder_pid}",
                                        ]
                                    ).strip()
                                )
                                if count >= required:
                                    break
                                if time.monotonic() > deadline_lock:
                                    raise TimeoutError(
                                        "separate physical lock waiters missing"
                                    )
                                time.sleep(0.02)
                            print(
                                f"PASS R04A PostgreSQL barrier observed {count} separate physical app connections",
                                flush=True,
                            )
                        elif action == "release-lock":
                            holder.stdin.write("ROLLBACK;\n\\q\n")
                            holder.stdin.flush()
                            holder.stdin.close()
                            holder.wait(timeout=5)
                        else:
                            raise ValueError("unknown synthetic control")
                        print("R04A_LIFECYCLE " + action, flush=True)
                        (state / "control/ack.tmp").write_text(action)
                        (state / "control/ack.tmp").replace(state / "control/ack")
                    time.sleep(0.05)
                if browser.returncode:
                    raise RuntimeError("R04 Chromium acceptance failed")
            finally:
                if browser.poll() is None:
                    browser.terminate()
                    try:
                        browser.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        browser.kill()
                        browser.wait(timeout=5)
            result = json.loads((state / "control/result.json").read_text())
            revoked_owner = subprocess.run(
                owner, cwd=ROOT, text=True, capture_output=True, timeout=30
            )
            assert revoked_owner.returncode != 0, (
                "owner CLI must not claim replay success from an old matching history row after binding revocation"
            )
            assert len(result["checks"]) > 0
            assert (
                run(
                    query
                    + [
                        "-c",
                        f'SELECT "WorkingGroupId"||\'|\'||"Quantity" FROM inventory.reservations WHERE "Id"=\'{result["reservationId"]}\'',
                    ]
                ).strip()
                == result["groups"][0] + "|2.000000"
            )
            assert result["groups"][0] != result["order"]

            def scalar(statement):
                return run(query + ["-c", statement]).strip()

            assert (
                scalar(
                    f"SELECT count(*) FROM workshop.installations WHERE \"PickId\"='{result['pickId']}'"
                )
                == "2"
            )
            for installation in result["installationIds"]:
                assert (
                    scalar(
                        f'SELECT count(*) FROM inventory.consumptions WHERE "InstallationId"=\'{installation}\' AND "Quantity"=0.5'
                    )
                    == "1"
                )
                assert (
                    scalar(
                        f"SELECT count(*) FROM inventory.carcass_return_installations WHERE \"InstallationId\"='{installation}' AND \"ReturnId\"='{result['carcassId']}'"
                    )
                    == "1"
                )
            for table, key, value in [
                ("inventory.picks", "Id", result["pickId"]),
                ("inventory.carcass_returns", "Id", result["carcassId"]),
            ]:
                assert (
                    scalar(
                        f'SELECT "WorkingGroupId"||\'|\'||"LineId" FROM {table} WHERE "{key}"=\'{value}\''
                    )
                    == result["groups"][0] + "|" + result["lines"][0]
                )
            # Independent Decimal oracle reads owning facts through the verifier only.
            for row in scalar(
                """SELECT s."Physical",coalesce((SELECT sum(r."Quantity") FROM inventory.reservations r WHERE (r."TenantId",r."LegalEntityId",r."SiteId",r."WarehouseId",r."CatalogItemId")=(s."TenantId",s."LegalEntityId",s."SiteId",s."WarehouseId",s."CatalogItemId")),0),coalesce((SELECT sum(c."Quantity") FROM inventory.consumptions c WHERE (c."TenantId",c."LegalEntityId",c."SiteId",c."WarehouseId",c."CatalogItemId")=(s."TenantId",s."LegalEntityId",s."SiteId",s."WarehouseId",s."CatalogItemId")),0) FROM inventory.stock s"""
            ).splitlines():
                physical, reserved, consumed = map(Decimal, row.split("|"))
                active = reserved - consumed
                available = physical - active
                assert physical >= 0 and active >= 0 and available >= 0
            assert (
                scalar(
                    'SELECT count(*) FROM organization_access.company_stock_profiles WHERE "Domain"=\'stock\' AND "Version"=1'
                )
                == "2"
            )
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert (
                    scalar(
                        f"SELECT has_table_privilege('runtime_app','organization_access.company_stock_profiles','{privilege}')"
                    )
                    == "f"
                )
            assert (
                scalar(
                    "SELECT has_function_privilege('runtime_app','organization_access.establish_stock_profile(uuid,uuid,uuid,uuid,uuid,text,uuid,uuid)','EXECUTE')"
                )
                == "f"
            )
            changed = scalar(
                f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{ctx['tenantId']}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{ctx['tenantId']}','{ctx['legalEntityId']}','{fixture['grantTargetMembershipId']}','{uuid.uuid4()}','ExternalToEnginia360','{uuid.uuid4()}','{uuid.uuid4()}'); ROLLBACK;"
            )
            assert changed.splitlines()[-1] == "stock_profile_immutable"
            run(command + ["run", "--rm", "--no-deps", "-T", "migrator"], timeout=90)
            manifest = json.loads((ROOT / "database/runtime/manifest.json").read_text())
            applied = dict(
                v.split("|")
                for v in scalar(
                    "SELECT id||'|'||checksum FROM runtime_migrations.applied ORDER BY id"
                ).splitlines()
            )
            assert applied == {v["id"]: v["sha256"] for v in manifest}
            # Private tmpfs backup/restore of synthetic stock and immutable authority; no retained volume.
            run(
                command
                + [
                    "exec",
                    "-T",
                    "postgres",
                    "sh",
                    "-c",
                    "pg_dump -U postgres -d runtime -Fc -f /tmp/r04-stock.dump && createdb -U postgres -O runtime_owner runtime_restore && pg_restore -U postgres -d runtime_restore /tmp/r04-stock.dump",
                ],
                timeout=60,
            )
            restored = query.copy()
            restored[restored.index("runtime")] = "runtime_restore"
            for table in (
                "organization_access.company_stock_profiles",
                "inventory.stock",
                "inventory.reservations",
                "inventory.picks",
                "workshop.installations",
                "inventory.consumptions",
                "inventory.carcass_returns",
                "inventory.carcass_return_installations",
            ):
                statement = f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') FROM {table} t"
                assert run(restored + ["-c", statement]).strip() == scalar(statement), (
                    table
                )
            print(
                "PASS R04A Decimal stock equations, source/coverage/idempotence, immutable owner-only profile, migration replay and exact synthetic backup/restore",
                flush=True,
            )
            evidence = Path(os.environ["TMPDIR"]) / ("r04a-evidence-pool" + pool)
            evidence.mkdir(exist_ok=True)
            (evidence / "result.json").write_text(json.dumps(result, indent=2))
            for screenshot in (state / "control").glob("*.png"):
                shutil.copyfile(screenshot, evidence / screenshot.name)
            print(
                "PASS R04A SQL reservation quantity/provenance; pool" + pool, flush=True
            )
        finally:
            for s in previous:
                signal.signal(s, signal.SIG_IGN)
            for holder in holders:
                if holder.poll() is None:
                    holder.terminate()
                    try:
                        holder.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        holder.kill()
                        holder.wait(timeout=5)
                for stream in (holder.stdin, holder.stdout):
                    if stream is not None and not stream.closed:
                        stream.close()
            try:
                r00.cleanup(command, project)
            finally:
                for s, h in previous.items():
                    signal.signal(s, h)
    assert r00.inventory("volume") == before_volumes
    assert set(run(["docker", "ps", "-q", "--no-trunc"]).splitlines()) == before_running
    print(
        "PASS R04A protected running containers and retained volumes unchanged",
        flush=True,
    )


if __name__ == "__main__":
    main()
