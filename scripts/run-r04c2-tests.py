#!/usr/bin/env python3
"""R04.c.2 synthetic TLS/OIDC/SQL acceptance; owned ephemeral lifecycle only."""

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
r00.CONFIG = ROOT / "compose.r04c2-test.yaml"
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
            "new-part-returns.create",
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
        sql += f"\nINSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.new-part-returns.create','{ctx['siteId']}','{ctx['warehouseId']}');"
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
            str(ROOT / "compose.r04c2-test.yaml"),
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
                deadline = time.monotonic() + 400
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
                        elif action.startswith("verify-return:"):
                            order, line, group, reservation, pick, receipt = [str(uuid.UUID(v)) for v in action.split(":")[1:]]
                            got=run(query+["-c", f'''SELECT "ReservationId"||'|'||"PickId"||'|'||"WorkingGroupId"||'|'||"WarehouseId"||'|'||"Quantity" FROM inventory.new_part_returns WHERE "Id"='{receipt}';''']).strip()
                            assert got == reservation+"|"+pick+"|"+group+"|"+ctx["warehouseId"]+"|1.000000", got
                            assert run(query+["-c", f'''SELECT "Physical" FROM inventory.stock WHERE "TenantId"='{ctx['tenantId']}' AND "WarehouseId"='{ctx['warehouseId']}' AND "CatalogItemId"='{data['partId']}';''']).strip()=="2.000000"
                            assert run(query+["-c",f'''SELECT "CommercialRevision" FROM workshop.orders WHERE "Id"='{order}';''']).strip()=="4"
                            assert run(query+["-c",f'''SELECT "Quantity"||'|'||"Version" FROM workshop.commercial_lines WHERE "Id"='{line}';''']).strip()=="3.000000|1"
                            for table,identifier in (("inventory.reservations",reservation),("inventory.picks",pick)):
                                assert run(query+["-c",f'''SELECT "Quantity" FROM {table} WHERE "Id"='{identifier}';''']).strip()=="2.000000"
                            assert run(query+["-c",f'''SELECT count(*) FROM inventory.new_part_returns x JOIN organization_access.memberships m ON m."Id"=x."MembershipId" AND m."TenantId"=x."TenantId" AND m."IdentitySubject"=x."OperatorId"::text WHERE x."Id"='{receipt}';''']).strip()=="1"
                            logs=run(command+["logs","--no-color","api"])
                            assert "new-part-returns 201 "+receipt in logs,"successful return technical audit must identify committed receipt, not original line placeholder"
                            print("PASS R04C2 SQL append-only return1 original warehouse/group provenance physical unchanged and audit receipt identity",flush=True)
                        elif action.startswith(("verify-return-provenance:","verify-return-pending:","verify-return-closed:")):
                            pick=str(uuid.UUID(action.split(":")[1]))
                            actor=run(query+["-c",f'''SELECT "IdentitySubject" FROM organization_access.memberships WHERE "Id"='{fixture['adminMembershipId']}';''']).strip()
                            invalid=f'''SET ROLE runtime_app; BEGIN; SELECT set_config('app.tenant_id','{ctx['tenantId']}',true); SELECT set_config('app.identity_subject','{actor}',true);
INSERT INTO inventory.new_part_returns SELECT '{uuid.uuid4()}',p."TenantId",p."ReservationId",p."Id",'{fixture['adminMembershipId']}',p."OrderId",p."LineId",p."WorkingGroupId",p."LegalEntityId",p."SiteId",'{second}',p."CatalogItemId",p."CatalogVersion",0.000001,clock_timestamp(),current_setting('app.identity_subject')::uuid FROM inventory.picks p WHERE p."Id"='{pick}'; COMMIT;'''
                            if action.startswith(("verify-return-pending:","verify-return-closed:")):
                                invalid=invalid.replace(f"'{second}',p.","p.\"WarehouseId\",p.")
                                result=subprocess.run(query,input=invalid,text=True,capture_output=True,timeout=30)
                                expected="new_return_not_open" if action.startswith("verify-return-closed:") else "new_return_pick_has_installations"
                                assert result.returncode!=0 and expected in result.stderr,"SQL must refuse source state: "+expected+result.stdout+result.stderr
                                print("PASS R04C2 SQL no installation whatsoever including Pending",flush=True)
                            else:
                                result=subprocess.run(query,input=invalid,text=True,capture_output=True,timeout=30)
                                assert result.returncode!=0 and "new_return_source_mismatch" in result.stderr, "SQL provenance constraint must reject forged original warehouse, got: "+result.stdout+result.stderr
                                print("PASS R04C2 SQL original picking provenance refuses forged warehouse",flush=True)
                                over=invalid.replace(f"'{second}',p.","p.\"WarehouseId\",p.").replace(",0.000001,",",2,")
                                result=subprocess.run(query,input=over,text=True,capture_output=True,timeout=30)
                                assert result.returncode!=0 and "new_return_exceeds_remaining" in result.stderr,"SQL must refuse return beyond original picked quota after compensation: "+result.stdout+result.stderr
                                print("PASS R04C2 SQL aggregate return bound",flush=True)
                                correct=invalid.replace(f"'{second}',p.","p.\"WarehouseId\",p.")
                                for field in ('ReservationId','OrderId','LineId','WorkingGroupId','LegalEntityId','SiteId','CatalogItemId','CatalogVersion'):
                                    value="9" if field=='CatalogVersion' else "'"+str(uuid.uuid4())+"'::uuid"
                                    forged=correct.replace('p."'+field+'"',value,1)
                                    result=subprocess.run(query,input=forged,text=True,capture_output=True,timeout=30)
                                    assert result.returncode!=0 and 'new_return_source_mismatch' in result.stderr,field+result.stdout+result.stderr
                                forged=correct.replace("'"+fixture['adminMembershipId']+"'","'"+str(uuid.uuid4())+"'",1)
                                result=subprocess.run(query,input=forged,text=True,capture_output=True,timeout=30)
                                assert result.returncode!=0 and 'new_return_actor_unauthorized' in result.stderr,'forged membership must not be accepted: '+result.stdout+result.stderr
                                print("PASS R04C2 SQL each provenance axis and verified membership independently enforced",flush=True)
                        elif action.startswith("verify-install-bound:"):
                            pick=str(uuid.UUID(action.split(":")[1]))
                            actor=run(query+["-c",f'''SELECT "IdentitySubject" FROM organization_access.memberships WHERE "Id"='{fixture['adminMembershipId']}';''']).strip()
                            raw=f'''SET ROLE runtime_app; BEGIN; SELECT set_config('app.tenant_id','{ctx['tenantId']}',true);
INSERT INTO workshop.installations SELECT '{uuid.uuid4()}',p."TenantId",p."Id",p."ReservationId",p."OrderId",p."WorkingGroupId",p."LineId",p."LegalEntityId",p."SiteId",p."WarehouseId",p."CatalogItemId",p."CatalogVersion",2,p."ConfigurationVersion",o."DocumentTypeId",o."ConfigurationVersion",clock_timestamp(),'{actor}',1,true FROM inventory.picks p JOIN workshop.orders o ON o."Id"=p."OrderId" WHERE p."Id"='{pick}'; COMMIT;'''
                            result=subprocess.run(query,input=raw,text=True,capture_output=True,timeout=30)
                            assert result.returncode!=0 and "installation_exceeds_unreturned" in result.stderr,"SQL Pending insertion must not bypass returned-quota allowance: "+result.stdout+result.stderr
                            print("PASS R04C2 SQL installation allowance excludes returned quota before consumption",flush=True)
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
                        elif action == "race-stock":
                            run(
                                query,
                                input=f"""UPDATE inventory.stock SET "Physical"=2+(SELECT coalesce(sum("Quantity"),0) FROM inventory.reservations WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}')-(SELECT coalesce(sum("Quantity"),0) FROM inventory.consumptions WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}') WHERE "TenantId"='{ctx["tenantId"]}' AND "WarehouseId"='{ctx["warehouseId"]}' AND "CatalogItemId"='{data["partId"]}';""",
                            )
                        elif action.startswith("tight-stock:"):
                            extra=Decimal(action.split(":")[1]); assert extra>=0
                            run(query,input=f'''UPDATE inventory.stock SET "Physical"={extra}+(SELECT coalesce(sum("Quantity"),0) FROM inventory.reservations WHERE "TenantId"='{ctx['tenantId']}' AND "WarehouseId"='{ctx['warehouseId']}')-(SELECT coalesce(sum("Quantity"),0) FROM inventory.reservation_releases WHERE "TenantId"='{ctx['tenantId']}' AND "WarehouseId"='{ctx['warehouseId']}')-(SELECT coalesce(sum("Quantity"),0) FROM inventory.new_part_returns WHERE "TenantId"='{ctx['tenantId']}' AND "WarehouseId"='{ctx['warehouseId']}')-(SELECT coalesce(sum("Quantity"),0) FROM inventory.consumptions WHERE "TenantId"='{ctx['tenantId']}' AND "WarehouseId"='{ctx['warehouseId']}') WHERE "TenantId"='{ctx['tenantId']}' AND "WarehouseId"='{ctx['warehouseId']}' AND "CatalogItemId"='{data['partId']}';''')
                        elif action in ("return-owner-revoke", "return-owner-restore"):
                            statement = f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{fixture['adminMembershipId']}' AND "Permission"='inventory.new-part-returns.create';'''
                            if action.endswith("restore"):
                                statement += f'''INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.new-part-returns.create','{ctx['siteId']}','{ctx['warehouseId']}');'''
                            run(query, input=statement)
                        elif action in ("capability-off", "capability-on"):
                            run(
                                query,
                                input=f'UPDATE organization_access.capability_activations SET "Enabled"={"true" if action.endswith("-on") else "false"} WHERE "LegalEntityId"=\'{ctx["legalEntityId"]}\' AND "Capability"=\'inventory\';',
                            )
                        elif action == "binding-revoke":
                            run(
                                query,
                                input=f'DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"=(SELECT "IdentitySubject"::uuid FROM organization_access.memberships WHERE "Id"=\'{fixture["adminMembershipId"]}\');',
                            )
                        elif action.startswith("target-return-scope:"):
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
                                grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.new-part-returns.create',{site},{warehouse});"
                            if scope == "common":
                                grant += f"INSERT INTO organization_access.common_edit_permissions VALUES ('{target}','{t}') ON CONFLICT DO NOTHING;"
                            run(query, input=grant)
                        elif action.startswith("target-return:"):
                            axis = action.split(":")[1]
                            denied = fixture["deniedContexts"][{"company": 0, "site": 1, "warehouse": 2}[axis]]
                            target = fixture["grantTargetMembershipId"]
                            t, c, s, w = [ctx[k] for k in ("tenantId", "legalEntityId", "siteId", "warehouseId")]
                            # Correct read scope; ONLY the release grant is moved along exactly one wrong axis.
                            grant = f"DELETE FROM organization_access.company_permissions WHERE \"MembershipId\"='{target}' AND \"Permission\" LIKE 'inventory.%';"
                            grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{c}','inventory.reservations.read','{s}','{w}');"
                            grant_c=denied['legalEntityId'] if axis=='company' else c
                            grant_s=denied['siteId'] if axis=='site' else s
                            grant_w=denied['warehouseId'] if axis=='warehouse' else w
                            # Deliberately adversarial synthetic permission tuple: change EXACTLY one axis.
                            # Authorization must validate the hierarchy, never accept this malformed combination.
                            assert sum((grant_c!=c,grant_s!=s,grant_w!=w))==1
                            grant += f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{t}','{grant_c}','inventory.new-part-returns.create','{grant_s}','{grant_w}');"
                            run(query, input=grant)
                        elif action.startswith("authority-return-seed:"):
                            ao,al,ag,ar,ap,ax=[str(uuid.UUID(v)) for v in action.split(":")[1:]]
                            other=fixture["deniedContexts"][0];t,c,site,w=ctx["tenantId"],other["legalEntityId"],other["siteId"],other["warehouseId"];admin=fixture["adminMembershipId"]
                            actor=run(query+["-c",f'''SELECT "IdentitySubject" FROM organization_access.memberships WHERE "Id"='{admin}';''']).strip()
                            seed=f"INSERT INTO organization_access.capability_activations VALUES ('{c}','workshop',true),('{c}','inventory',true); INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{admin}','{t}','{c}','workshop.orders.read',NULL,NULL);"
                            for permission in ("inventory.reservations.read","inventory.new-part-returns.create"):
                                seed+=f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{admin}','{t}','{c}','{permission}','{site}','{w}');"
                            seed+=f'''INSERT INTO inventory.reservations VALUES ('{ar}','{t}','{ao}','{al}','{c}','{site}','{w}','{data['partId']}',8,1,'{ag}');
INSERT INTO inventory.picks VALUES ('{ap}','{t}','{ar}','{ao}','{ag}','{al}','{c}','{site}','{w}','{data['partId']}',8,1,1,'SYNTHETIC historical origin',NULL,'{ap}',clock_timestamp(),'{actor}');
BEGIN; SET LOCAL session_replication_role=replica; INSERT INTO inventory.new_part_returns VALUES ('{ax}','{t}','{ar}','{ap}','{admin}','{ao}','{al}','{ag}','{c}','{site}','{w}','{data['partId']}',8,0.25,clock_timestamp(),'{actor}'); COMMIT;'''
                            run(query,input=seed)
                        elif action == "authority-external":
                            other = fixture["deniedContexts"][0]
                            t, c = ctx["tenantId"], other["legalEntityId"]
                            run(query, input=f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}','{fixture['adminMembershipId']}','{uuid.uuid4()}','ExternalToEnginia360','{uuid.uuid4()}','{uuid.uuid4()}'); COMMIT;")
                        elif action in ("hold-stock","hold-return-read") or action.startswith(("hold-line:", "hold-order:")):
                            holder = subprocess.Popen(
                                query + ["-f", "-"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                text=True,
                            )
                            holders.append(holder)
                            if action == "hold-return-read":
                                run(query,input='''CREATE SEQUENCE inventory.synthetic_return_read_sequence; GRANT USAGE,SELECT ON SEQUENCE inventory.synthetic_return_read_sequence TO runtime_app;
CREATE OR REPLACE FUNCTION inventory.pick_returned(tenant uuid,pick uuid) RETURNS numeric LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,inventory AS $$ DECLARE q numeric; BEGIN SELECT coalesce(sum("Quantity"),0) INTO q FROM inventory.new_part_returns WHERE "TenantId"=tenant AND "PickId"=pick AND tenant::text=current_setting('app.tenant_id',true); IF nextval('inventory.synthetic_return_read_sequence')=1 THEN PERFORM pg_advisory_xact_lock(hashtextextended('inventory:synthetic:return-read',0)); END IF; RETURN q; END $$;''')
                                lock="BEGIN; SELECT pg_advisory_lock(hashtextextended('inventory:synthetic:return-read',0));"
                            elif action == "hold-stock":
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
                            waiters=run(query+["-c","SELECT pid||':'||pg_blocking_pids(pid)::text FROM pg_stat_activity WHERE usename='runtime_app' AND cardinality(pg_blocking_pids(pid))>0 ORDER BY pid"]).strip()
                            print(f"R04C2_SQL_BARRIER controller_pid={holder_pid} app_waiters={waiters}",flush=True)
                            print(
                                f"PASS R04A PostgreSQL barrier observed {count} separate physical app connections",
                                flush=True,
                            )
                        elif action == "restore-return-read":
                            import re
                            original=re.search(r'CREATE FUNCTION inventory.pick_returned\(.*?\$\$;', (ROOT/'database/runtime/migrations/0024_new_part_returns.sql').read_text(),re.S)
                            assert original
                            run(query,input=original.group(0).replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)+" DROP SEQUENCE inventory.synthetic_return_read_sequence;")
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
            for screenshot in (state / "control").glob("return-*.png"):
                destination=Path(os.environ["TMPDIR"])/("r04c2-pool"+pool+"-"+screenshot.name)
                shutil.copyfile(screenshot,destination)
                print("R04C2_SCREENSHOT "+str(destination),flush=True)
            result = json.loads((state / "control/result.json").read_text())
            assert result["checks"], "named browser assertions required"
            def scalar(statement): return run(query+["-c",statement]).strip()
            assert result["groups"][0]!=result["order"]
            assert scalar(f'''SELECT "Quantity"||'|'||"WorkingGroupId" FROM inventory.new_part_returns WHERE "Id"='{result['returnId']}';''')=='1.000000|'+result['groups'][0]
            for key,quantity in (("pendingId","0.500000"),("downstreamInstall","1.000000")):
                assert scalar(f'''SELECT count(*)||'|'||min("Quantity") FROM inventory.consumptions WHERE "InstallationId"='{result[key]}';''')=='1|'+quantity
            assert scalar(f'''SELECT "WorkingGroupId"||'|'||"Quantity" FROM inventory.picks WHERE "Id"='{result['downstreamPick']}';''')==result['groups'][0]+'|1.000000'
            assert scalar(f'''SELECT "WorkingGroupId"||'|'||"Quantity" FROM inventory.carcass_returns WHERE "Id"='{result['carcassId']}';''')==result['groups'][0]+'|1.500000'
            assert scalar(f'''SELECT "SourceRevision"||'|'||("Summary"->>'total') FROM billing.invoices WHERE "Id"='{result['invoiceId']}';''')==str(result['revision'])+'|3.660000'
            assert scalar(f'''SELECT count(*) FROM accounting.journal_entries WHERE "Id"='{result['journalId']}' AND "TotalDebit"="TotalCredit" AND "TotalDebit"=3.66;''')=='1'
            assert scalar(f'''SELECT sum("Debit")=sum("Credit") FROM accounting.journal_entry_lines WHERE "EntryId"='{result['journalId']}';''')=='t'
            assert json.loads(scalar(f'''SELECT "Summary" FROM workshop.administrative_requests WHERE "Id"='{result['externalId']}';'''))==result['fsnapshot']
            assert scalar("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='inventory.new_part_returns'::regclass")=='t'
            assert scalar("SELECT has_table_privilege('runtime_app','inventory.new_part_returns','SELECT') AND has_table_privilege('runtime_app','inventory.new_part_returns','INSERT')")=='t'
            for operation in ('UPDATE','DELETE','TRUNCATE'):
                assert scalar(f"SELECT has_table_privilege('runtime_app','inventory.new_part_returns','{operation}')")=='f'
                sql={"UPDATE":"UPDATE inventory.new_part_returns SET \"Quantity\"=0.1", "DELETE":"DELETE FROM inventory.new_part_returns", "TRUNCATE":"TRUNCATE inventory.new_part_returns"}[operation]
                denied=subprocess.run(query,input=f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{ctx['tenantId']}',true); {sql}; COMMIT;",text=True,capture_output=True,timeout=30)
                assert denied.returncode!=0 and 'new_part_return_is_immutable' in denied.stderr,operation+denied.stderr
            for tenant in ('',ext['tenantId']):
                hidden=scalar(f'''SET ROLE runtime_app; BEGIN; SELECT set_config('app.tenant_id','{tenant}',true); SELECT count(*) FROM inventory.new_part_returns WHERE "Id"='{result['returnId']}'; COMMIT;''').splitlines()[-1]
                assert hidden=='0',"forced RLS hides exact receipt without/with foreign tenant"
            applied=dict(row.split('|') for row in scalar("SELECT id||'|'||checksum FROM runtime_migrations.applied ORDER BY id").splitlines())
            assert applied=={e['id']:e['sha256'] for e in json.loads((ROOT/'database/runtime/manifest.json').read_text())}
            assert scalar('SELECT count(*) FROM inventory.picks p WHERE coalesce((SELECT sum(x."Quantity") FROM inventory.new_part_returns x WHERE x."PickId"=p."Id"),0)+coalesce((SELECT sum(i."Quantity") FROM workshop.installations i WHERE i."PickId"=p."Id"),0)>p."Quantity"')=='0','no returned quota installed, including Pending'
            assert scalar('SELECT count(*) FROM inventory.picks p WHERE coalesce((SELECT sum(x."Quantity") FROM inventory.new_part_returns x WHERE x."PickId"=p."Id"),0)+coalesce((SELECT sum(c."Quantity") FROM inventory.consumptions c WHERE c."PickId"=p."Id"),0)>p."Quantity"')=='0','no returned quota consumed'
            print("PASS R04C2 SQL global pick return/install/consume bounds include all concurrency winners and Pending facts",flush=True)
            print("PASS R04C2 persisted SQL downstream groups/q6/sourceRevision/internal journal/external pinned summary, forced RLS/minimal grants/owner update-delete-truncate denial/manifest checksums",flush=True)
            print("PASS R04C2 real TLS/OIDC API and SQL: " + str(len(result["checks"])) + " named checks", flush=True)
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
