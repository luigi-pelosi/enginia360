-- Upgrade existing currencies without replacing rows or seed data.
BEGIN;
ALTER TABLE foundation.currency ADD COLUMN version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991);
CREATE FUNCTION foundation.bump_currency_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.version := OLD.version + 1;
    RETURN NEW;
END;
$$;
CREATE TRIGGER bump_currency_version BEFORE UPDATE ON foundation.currency FOR EACH ROW EXECUTE FUNCTION foundation.bump_currency_version();
COMMIT;
