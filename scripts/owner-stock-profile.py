#!/usr/bin/env python3
"""Owner/trusted offline initial company stock setup, after identity/source verification.
Technical evidence reference records an out-of-band check, never performs identity
verification. No app endpoint, delegated setup, pilot values, provisioning or ERP call.
An established profile cannot be changed through this bounded initial-setup tool.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

IDS = {
    "commandId",
    "tenantId",
    "legalEntityId",
    "actorMembershipId",
    "verificationReference",
    "sourceId",
    "profileId",
}
FIELDS = IDS | {"domain", "direction", "expectedVersion"}


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("explicit closed company stock setup input required")
    try:
        if any(
            not isinstance(value[k], str)
            or str(uuid.UUID(value[k])) != value[k]
            or uuid.UUID(value[k]).int == 0
            for k in IDS
        ):
            raise ValueError("canonical nonempty technical references required")
    except (AttributeError, TypeError):
        raise ValueError("canonical technical references required") from None
    if value["domain"] != "stock" or value["direction"] not in (
        "Enginia360ToExternal",
        "ExternalToEnginia360",
    ):
        raise ValueError("explicit stock direction required")
    if type(value["expectedVersion"]) is not int or value["expectedVersion"] != 0:
        raise ValueError("initial setup only; existing authority cannot be retargeted")
    return value


def apply(value):
    value = validate(value)
    if os.environ.get("PGSSLMODE") != "verify-full" or not os.environ.get(
        "PGSSLROOTCERT"
    ):
        raise ValueError("CA-verified TLS required")
    sql = """BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',:'tenantId',true);
SELECT organization_access.establish_stock_profile(:'commandId'::uuid,:'tenantId'::uuid,:'legalEntityId'::uuid,:'actorMembershipId'::uuid,:'verificationReference'::uuid,:'direction',:'sourceId'::uuid,:'profileId'::uuid);
COMMIT;
SELECT set_config('app.tenant_id',:'tenantId',false);
SELECT count(*) FROM organization_access.company_stock_profiles WHERE "CommandId"=:'commandId'::uuid AND "TenantId"=:'tenantId'::uuid AND "LegalEntityId"=:'legalEntityId'::uuid AND "ActorMembershipId"=:'actorMembershipId'::uuid AND "VerificationReference"=:'verificationReference'::uuid AND "Domain"='stock' AND "Version"=1 AND "Direction"=:'direction' AND "SourceId"=:'sourceId'::uuid AND "ProfileId"=:'profileId'::uuid;
"""
    args = ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
    for key in IDS | {"direction"}:
        args += ["-v", key + "=" + value[key]]
    result = subprocess.run(args, input=sql, text=True, capture_output=True, timeout=30)
    lines = result.stdout.splitlines()
    if (
        result.returncode
        or len(lines) < 4
        or lines[-3] not in ("applied", "replayed")
        or lines[-1] != "1"
    ):
        raise ValueError("owner setup refused or exact readback failed")
    print(
        "Company stock profile committed/replayed and exact immutable history read back. No provisioning or ERP call."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        apply(json.loads(args.input.read_text()))
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        print(
            "Stock setup refused. Verify existing trusted binding/membership, explicit company/source, evidence reference, initial version, TLS and nonprivileged owner connection. No credentials logged.",
            file=sys.stderr,
        )
        sys.exit(1)
