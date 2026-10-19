-- Only for disposable acceptance, or after exporting and approving loss of picking facts.
-- Production rollback: disable Inventory, retain schema/data, redeploy previous image.
BEGIN;
DROP TABLE IF EXISTS inventory.picks;
DROP TABLE IF EXISTS inventory.picking_locations;
DROP TABLE IF EXISTS inventory.picking_policies;
COMMIT;
