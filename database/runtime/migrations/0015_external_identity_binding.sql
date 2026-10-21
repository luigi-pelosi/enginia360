-- Technical identity bridge only. No membership, grant, tenant or first-login setup.
-- Issuer is matched only after cryptographic authentication by the trusted handler.
CREATE TABLE organization_access.external_identity_bindings (
    "InternalIdentityId" uuid PRIMARY KEY CHECK (
        "InternalIdentityId" <> '00000000-0000-0000-0000-000000000000'::uuid
    ),
    "Issuer" text COLLATE "C" NOT NULL CHECK (
        octet_length("Issuer") BETWEEN 9 AND 2048
        AND "Issuer" ~ '^https://[^[:space:]?#]+$'
    ),
    "Subject" varchar(255) COLLATE "C" NOT NULL CHECK (
        octet_length("Subject") BETWEEN 1 AND 255
        AND "Subject" ~ '^[ -~]+$'
    ),
    UNIQUE ("Issuer", "Subject")
);

ALTER TABLE organization_access.external_identity_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.external_identity_bindings FORCE ROW LEVEL SECURITY;

CREATE POLICY verified_external_identity
    ON organization_access.external_identity_bindings
    FOR SELECT
    USING (
        "Issuer" = current_setting('app.identity_issuer', true) COLLATE "C"
        AND "Subject" = current_setting('app.external_subject', true) COLLATE "C"
    );

REVOKE ALL ON organization_access.external_identity_bindings FROM PUBLIC;
GRANT SELECT ON organization_access.external_identity_bindings TO :"app_user";
