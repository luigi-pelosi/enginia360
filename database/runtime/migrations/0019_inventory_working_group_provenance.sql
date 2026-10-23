-- R03.a: a reservation carries the real working group of its Workshop line (owner-public ReservationLine.WorkingGroupId).
ALTER TABLE inventory.reservations NO FORCE ROW LEVEL SECURITY;
ALTER TABLE inventory.reservations ADD COLUMN "WorkingGroupId" uuid;
-- Baseline guarantee: until this unit every working group equalled its order.
UPDATE inventory.reservations SET "WorkingGroupId" = "OrderId";
ALTER TABLE inventory.reservations ALTER COLUMN "WorkingGroupId" SET NOT NULL;
ALTER TABLE inventory.reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.reservations FORCE ROW LEVEL SECURITY;
