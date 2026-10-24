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
r00.CONFIG = ROOT / "compose.r04c1-test.yaml"
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
            "reservations.release",
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
        sql += f"\nINSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.reservations.release','{ctx['siteId']}','{ctx['warehouseId']}');"
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
            str(ROOT / "compose.r04c1-test.yaml"),
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
                command + ["run", "--rm", "--no-deps", "-T", "-e", "RELEASE_POOL=" + pool, "browser"], cwd=ROOT
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
                        elif action == "external-local-setup":
                            t,c=ext['tenantId'],ext['legalEntityId']
                            run(query,input=f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}',(SELECT \"Id\" FROM organization_access.memberships WHERE \"TenantId\"='{t}'),'{uuid.uuid4()}','Enginia360ToExternal','{uuid.uuid4()}','{uuid.uuid4()}'); COMMIT;")
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
                        elif action in ("release-owner-revoke", "release-owner-restore"):
                            statement = f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{fixture['adminMembershipId']}' AND "Permission"='inventory.reservations.release';'''
                            if action.endswith("restore"):
                                statement += f'''INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.reservations.release','{ctx['siteId']}','{ctx['warehouseId']}');'''
                            run(query, input=statement)
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
                                grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.reservations.release',{site},{warehouse});"
                            if scope == "common":
                                grant += f"INSERT INTO organization_access.common_edit_permissions VALUES ('{target}','{t}') ON CONFLICT DO NOTHING;"
                            run(query, input=grant)
                        elif action.startswith("target-release:"):
                            axis = action.split(":")[1]
                            denied = fixture["deniedContexts"][{"company": 0, "site": 1, "warehouse": 2}[axis]]
                            target = fixture["grantTargetMembershipId"]
                            t, c, s, w = [ctx[k] for k in ("tenantId", "legalEntityId", "siteId", "warehouseId")]
                            # Correct read scope; ONLY the release grant is moved along exactly one wrong axis.
                            grant = f"DELETE FROM organization_access.company_permissions WHERE \"MembershipId\"='{target}' AND \"Permission\" LIKE 'inventory.%';"
                            grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.reservations.read','{s}','{w}');"
                            grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{denied['legalEntityId']}','inventory.reservations.release','{denied['siteId']}','{denied['warehouseId']}');"
                            if axis == "site":
                                grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.reservations.release','{denied['siteId']}',NULL);"
                            assert (denied["legalEntityId"] != c) == (axis == "company")
                            assert (denied["siteId"] != s) == (axis in ("company", "site"))
                            assert denied["warehouseId"] != w
                            run(query, input=grant)
                        elif action.startswith("authority-seed:"):
                            a_order, a_line, a_group, a_res, a_rel = [str(uuid.UUID(v)) for v in action.split(":")[1:]]
                            other = fixture["deniedContexts"][0]
                            t, c, s, w = ctx["tenantId"], other["legalEntityId"], other["siteId"], other["warehouseId"]
                            admin = fixture["adminMembershipId"]
                            seed = f"INSERT INTO organization_access.capability_activations VALUES ('{c}','workshop',true),('{c}','inventory',true);"
                            seed += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{admin}','{t}','{c}','workshop.orders.read',NULL,NULL);"
                            for permission in ("read", "release"):
                                seed += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{admin}','{t}','{c}','inventory.reservations.{permission}','{s}','{w}');"
                            # Synthetic pre-existing receipt: owner-seeded with triggers off because no local authority can create one.
                            seed += f"INSERT INTO inventory.reservations VALUES ('{a_res}','{t}','{a_order}','{a_line}','{c}','{s}','{w}','{data['partId']}',8,1,'{a_group}');"
                            seed += f"BEGIN; SET LOCAL session_replication_role=replica; INSERT INTO inventory.reservation_releases VALUES ('{a_rel}','{t}','{a_res}','{a_order}','{a_line}','{a_group}','{c}','{s}','{w}','{data['partId']}',8,0.25,clock_timestamp(),'{uuid.uuid4()}'); COMMIT;"
                            run(query, input=seed)
                        elif action == "authority-external":
                            other = fixture["deniedContexts"][0]
                            t, c = ctx["tenantId"], other["legalEntityId"]
                            run(query, input=f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}','{fixture['adminMembershipId']}','{uuid.uuid4()}','ExternalToEnginia360','{uuid.uuid4()}','{uuid.uuid4()}'); COMMIT;")
                        elif action == "hold-stock" or action.startswith(("hold-line:", "hold-order:")):
                            holder = subprocess.Popen(
                                query + ["-f", "-"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                text=True,
                            )
                            holders.append(holder)
                            if action == "hold-stock":
                                lock = f"""BEGIN; SELECT "Physical" FROM inventory.stock WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}' AND "CatalogItemId"='{data["partId"]}' FOR UPDATE;"""
                            elif action.startswith("hold-order:"):
                                order = str(uuid.UUID(action.split(":")[1]))
                                lock = f"BEGIN; SELECT pg_advisory_lock(hashtextextended('{order}',0));"
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
            def scalar(statement):
                return run(query + ["-c", statement]).strip()
            assert result["groups"][0] != result["order"]
            assert scalar(f'SELECT "WorkingGroupId"||\'|\'||"Quantity" FROM inventory.reservations WHERE "Id"=\'{result["reservationId"]}\'') == result["groups"][0]+"|2.000000"
            assert scalar(f'SELECT "ReservationId"||\'|\'||"Quantity"||\'|\'||"WorkingGroupId" FROM inventory.reservation_releases WHERE "Id"=\'{result["releaseId"]}\'') == result["reservationId"]+"|1.000000|"+result["groups"][0]
            assert scalar(f'SELECT "Physical" FROM inventory.stock WHERE "TenantId"=\'{ctx["tenantId"]}\' AND "WarehouseId"=\'{ctx["warehouseId"]}\' AND "CatalogItemId"=\'{data["partId"]}\'') == "1.000000"
            assert scalar(f'SELECT "Quantity" FROM inventory.consumptions WHERE "InstallationId"=\'{result["installId"]}\'') == "1.000000"
            assert scalar(f'SELECT "WorkingGroupId" FROM workshop.installations WHERE "Id"=\'{result["installId"]}\'') == result["groups"][0]
            assert scalar(f'SELECT "SourceRevision" FROM billing.invoices WHERE "Id"=\'{result["invoiceId"]}\'') == "5"
            for authority_reservation in result["authorityReservations"]:
                assert scalar(f'SELECT count(*)||\'|\'||coalesce(sum("Quantity"),0) FROM inventory.reservation_releases WHERE "ReservationId"=\'{authority_reservation}\'') == "1|0.250000", "missing/external authority must leave exactly the seeded receipt"
            print("PASS R04C1 SQL missing/external authority wrote no release ledger row", flush=True)
            forged = subprocess.run(query, input=f'''SET ROLE runtime_app; BEGIN; SELECT set_config('app.tenant_id','{ctx['tenantId']}',true);
INSERT INTO inventory.reservation_releases SELECT '{uuid.uuid4()}',r."TenantId",r."Id",r."OrderId",r."LineId",r."WorkingGroupId",r."LegalEntityId",r."SiteId",r."WarehouseId",r."CatalogItemId",r."CatalogVersion",999,clock_timestamp(),'{uuid.uuid4()}' FROM inventory.reservations r WHERE r."Id"='{result['reservationId']}'; COMMIT;''', text=True, capture_output=True, timeout=30)
            assert forged.returncode != 0, 'SQL must reject release exceeding original quantity / picked source; not application-only validation'
            print("PASS R04C1 SQL raw over-release/picked-source refusal", flush=True)
            print("PASS R04C1 real SQL original reservation, compensation/provenance and unchanged physical", flush=True)
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
