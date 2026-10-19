-- Test-only policy evolution; old orders keep their referenced version.
INSERT INTO workshop.document_types
SELECT "Id", "TenantId", "LegalEntityId", 2, 'Nuova versione sintetica disabilitata', false
FROM workshop.document_types
WHERE "Id" = '11111111-5555-0000-0000-000000000001' AND "Version" = 1
ON CONFLICT DO NOTHING;
