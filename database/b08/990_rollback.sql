-- DESTRUCTIVE synthetic-fixture rollback only, never a compensation of real installed parts.
-- Stop writes and retain a full backup before any application/schema rollback.
BEGIN;
DO $$ BEGIN
 IF to_regclass('inventory.consumptions') IS NOT NULL THEN
  UPDATE inventory.stock s SET "Physical"=s."Physical"+c.quantity
  FROM (SELECT "TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId",sum("Quantity") quantity
        FROM inventory.consumptions GROUP BY 1,2,3,4,5) c
  WHERE s."TenantId"=c."TenantId" AND s."LegalEntityId"=c."LegalEntityId" AND s."SiteId"=c."SiteId"
    AND s."WarehouseId"=c."WarehouseId" AND s."CatalogItemId"=c."CatalogItemId";
 END IF;
END $$;
DROP TABLE IF EXISTS inventory.consumptions;
DROP TABLE IF EXISTS workshop.installations;
-- Preserve B06's pre-existing UPDATE ("Physical") grant: SELECT FOR UPDATE depends on it.
COMMIT;
