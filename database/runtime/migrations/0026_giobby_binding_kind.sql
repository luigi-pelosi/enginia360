-- R05.b.1: permit only the bounded sales-order adapter beside the existing synthetic protocol.
-- No history rewrite/backfill, no new table, permission, authority or provider identity.
ALTER TABLE workshop.administrative_bindings DROP CONSTRAINT "administrative_bindings_Kind_check";
ALTER TABLE workshop.administrative_bindings ADD CONSTRAINT "administrative_bindings_Kind_check"
 CHECK ("Kind" IN ('SimulatorV1','GiobbyV1'));
