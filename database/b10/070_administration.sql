BEGIN;
-- Charter 7.3: one declared administrative authority per company, versioned customizing (D9). No default destination.
CREATE TABLE IF NOT EXISTS workshop.administrative_destinations (
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "Version" integer NOT NULL CHECK ("Version">0),
 "Destination" varchar(30) NOT NULL CHECK ("Destination" IN ('External')),
 PRIMARY KEY ("TenantId","LegalEntityId","Version")
);
-- D37/D39/D73: durable technical closure, recorded only with the configured carcass requirement satisfied.
CREATE TABLE IF NOT EXISTS workshop.technical_closures (
 "OrderId" uuid PRIMARY KEY,
 "Id" uuid NOT NULL UNIQUE CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">=0),
 "ClosedAt" timestamptz NOT NULL,
 "OperatorId" uuid NOT NULL
);
-- Immutable owner-local request: the q6 commercial snapshot at technical closure (D66/D67), never recalculated.
CREATE TABLE IF NOT EXISTS workshop.administrative_requests (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "OrderId" uuid NOT NULL UNIQUE REFERENCES workshop.technical_closures("OrderId"),
 "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL,
 "Destination" varchar(30) NOT NULL,
 "DestinationVersion" integer NOT NULL CHECK ("DestinationVersion">0),
 "ContractVersion" integer NOT NULL CHECK ("ContractVersion"=1),
 "Revision" integer NOT NULL CHECK ("Revision">=0),
 "NetAmount" numeric(18,6) NOT NULL CHECK ("NetAmount">=0),
 "TaxAmount" numeric(18,6) NOT NULL CHECK ("TaxAmount">=0),
 "Total" numeric(18,6) NOT NULL CHECK ("Total"="NetAmount"+"TaxAmount"),
 "Currency" char(3) NOT NULL,
 "Summary" jsonb NOT NULL,
 "RequestedAt" timestamptz NOT NULL,
 "OperatorId" uuid NOT NULL
);
-- Outbox row inserted in the same Workshop transaction as the request; delivery state belongs to the connector.
CREATE TABLE IF NOT EXISTS workshop.administrative_outbox (
 "RequestId" uuid PRIMARY KEY REFERENCES workshop.administrative_requests("Id"),
 "TenantId" uuid NOT NULL,
 "CreatedAt" timestamptz NOT NULL
);
-- D40: only a business outcome ends the outbox entry. Received/acquired is never recorded here.
CREATE TABLE IF NOT EXISTS workshop.administrative_outcomes (
 "RequestId" uuid PRIMARY KEY REFERENCES workshop.administrative_requests("Id"),
 "TenantId" uuid NOT NULL,
 "Status" varchar(20) NOT NULL CHECK ("Status" IN ('Confirmed','Rejected')),
 "ExternalReference" varchar(64),
 "RejectionCode" varchar(64),
 "RecordedAt" timestamptz NOT NULL,
 CHECK (("Status"='Confirmed' AND "ExternalReference" IS NOT NULL AND "RejectionCode" IS NULL)
     OR ("Status"='Rejected' AND "ExternalReference" IS NULL AND "RejectionCode" IS NOT NULL))
);
-- A stable external reference confirms at most one request of the tenant.
CREATE UNIQUE INDEX IF NOT EXISTS administrative_outcome_reference ON workshop.administrative_outcomes("TenantId","ExternalReference") WHERE "ExternalReference" IS NOT NULL;
CREATE TABLE IF NOT EXISTS workshop.administrative_closures (
 "OrderId" uuid PRIMARY KEY REFERENCES workshop.technical_closures("OrderId"),
 "Id" uuid NOT NULL UNIQUE CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "RequestId" uuid NOT NULL UNIQUE REFERENCES workshop.administrative_outcomes("RequestId"),
 "ExternalReference" varchar(64) NOT NULL,
 "ClosedAt" timestamptz NOT NULL,
 "OperatorId" uuid NOT NULL
);
CREATE SCHEMA IF NOT EXISTS integrations;
-- Connector-owned technical delivery state. Mutable, but never a business outcome by itself.
CREATE TABLE IF NOT EXISTS integrations.administrative_dispatches (
 "RequestId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "State" varchar(20) NOT NULL CHECK ("State" IN ('Queued','Received','Retrying','Completed','Rejected')),
 "Attempts" integer NOT NULL CHECK ("Attempts">=0),
 "LastAttemptAt" timestamptz,
 "NextAttemptAt" timestamptz NOT NULL,
 "LeaseUntil" timestamptz,
 "ExternalReference" varchar(64),
 "RejectionCode" varchar(64),
 "LastError" varchar(64),
 "UpdatedAt" timestamptz NOT NULL
);
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['workshop.administrative_destinations','workshop.technical_closures','workshop.administrative_requests',
   'workshop.administrative_outbox','workshop.administrative_outcomes','workshop.administrative_closures','integrations.administrative_dispatches'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
-- The dispatcher must discover pending work across tenants before it can set a tenant context.
-- A dedicated NOLOGIN owner may read only the two outbox tables; the function returns envelopes, never payloads.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='enginia360_outbox_reader') THEN
  CREATE ROLE enginia360_outbox_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
 END IF;
END $$;
GRANT USAGE ON SCHEMA workshop TO enginia360_outbox_reader;
GRANT SELECT ("TenantId","RequestId","CreatedAt") ON workshop.administrative_outbox TO enginia360_outbox_reader;
GRANT SELECT ("RequestId") ON workshop.administrative_outcomes TO enginia360_outbox_reader;
CREATE OR REPLACE FUNCTION workshop.pending_administrative_outbox(max_items integer)
RETURNS TABLE ("TenantId" uuid, "RequestId" uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
 SELECT o."TenantId", o."RequestId" FROM workshop.administrative_outbox o
 WHERE NOT EXISTS (SELECT 1 FROM workshop.administrative_outcomes r WHERE r."RequestId"=o."RequestId")
 ORDER BY o."CreatedAt", o."RequestId" LIMIT least(greatest(max_items,1),100)
$$;
ALTER FUNCTION workshop.pending_administrative_outbox(integer) OWNER TO enginia360_outbox_reader;
REVOKE ALL ON FUNCTION workshop.pending_administrative_outbox(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.pending_administrative_outbox(integer) TO :"app_user";
GRANT SELECT ON workshop.administrative_destinations TO :"app_user";
GRANT SELECT, INSERT ON workshop.technical_closures, workshop.administrative_requests, workshop.administrative_outbox,
 workshop.administrative_outcomes, workshop.administrative_closures TO :"app_user";
GRANT USAGE ON SCHEMA integrations TO :"app_user";
GRANT SELECT, INSERT ON integrations.administrative_dispatches TO :"app_user";
GRANT UPDATE ("State","Attempts","LastAttemptAt","NextAttemptAt","LeaseUntil","ExternalReference","RejectionCode","LastError","UpdatedAt")
 ON integrations.administrative_dispatches TO :"app_user";
COMMIT;
