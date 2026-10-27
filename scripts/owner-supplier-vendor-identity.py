#!/usr/bin/env python3
"""Owner/trusted offline setup of the Giobby vendor identity of a supplier counterparty, per company (D88).

The identity is an opaque vendor ID plus the exact vendor name used for the lookup, nothing else. It is a
company extension, never part of the tenant-wide shared master. No app endpoint, no delegated setup, no
ERP call and no credential: the technical evidence reference records an out-of-band check and is not
identity verification. The counterparty must already hold the supplier role.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

IDS = {"commandId", "tenantId", "legalEntityId", "counterpartyId", "actorMembershipId", "verificationReference"}
FIELDS = IDS | {"expectedRevision", "vendorId", "vendorName"}


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("explicit closed vendor identity input required")
    try:
        if any(not isinstance(value[k], str) or str(uuid.UUID(value[k])) != value[k] or uuid.UUID(value[k]).int == 0 for k in IDS):
            raise ValueError("canonical nonempty technical references required")
    except (AttributeError, TypeError):
        raise ValueError("canonical technical references required") from None
    if type(value["expectedRevision"]) is not int or not 0 <= value["expectedRevision"] < 2**31:
        raise ValueError("exact nonnegative expected revision required")
    if not isinstance(value["vendorId"], str) or re.fullmatch(r"[!-~]{1,64}", value["vendorId"]) is None:
        raise ValueError("opaque vendor id of 1-64 printable characters required")
    name = value["vendorName"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200 or re.search(r"[\x00-\x1f\x7f]", name):
        raise ValueError("exact vendor name of 1-200 characters required")
    return value


def apply(value):
    value = validate(value)
    if os.environ.get("PGSSLMODE") != "verify-full" or not os.environ.get("PGSSLROOTCERT"):
        raise ValueError("CA-verified TLS required")
    sql = """BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',:'tenantId',true), set_config('app.legal_entity_id',:'legalEntityId',true);
SELECT counterparties.establish_giobby_vendor_identity(:'commandId'::uuid,:'tenantId'::uuid,:'legalEntityId'::uuid,:'counterpartyId'::uuid,:'actorMembershipId'::uuid,:'verificationReference'::uuid,:'expectedRevision'::integer,:'vendorId',:'vendorName');
COMMIT;
SELECT set_config('app.tenant_id',:'tenantId',false), set_config('app.legal_entity_id',:'legalEntityId',false);
SELECT count(*) FROM counterparties.giobby_vendor_identity_history WHERE "CommandId"=:'commandId'::uuid AND "TenantId"=:'tenantId'::uuid AND "LegalEntityId"=:'legalEntityId'::uuid AND "CounterpartyId"=:'counterpartyId'::uuid AND "ActorMembershipId"=:'actorMembershipId'::uuid AND "VerificationReference"=:'verificationReference'::uuid AND "VendorId"=:'vendorId' AND "VendorName"=btrim(:'vendorName');
"""
    args = ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
    for key in sorted(IDS | {"expectedRevision", "vendorId", "vendorName"}):
        args += ["-v", key + "=" + str(value[key])]
    result = subprocess.run(args, input=sql, text=True, capture_output=True, timeout=30)
    lines = result.stdout.splitlines()
    if result.returncode or len(lines) < 4 or lines[-3] not in ("applied", "replayed") or lines[-1] != "1":
        raise ValueError("owner setup refused or exact readback failed")
    print("Giobby vendor identity committed/replayed and exact immutable history read back. No ERP call.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        apply(json.loads(args.input.read_text()))
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        print("Vendor identity setup refused. Verify trusted binding/membership, supplier role, company/counterparty, expected revision, TLS and nonprivileged owner connection. No credentials logged.", file=sys.stderr)
        sys.exit(1)
