-- Rimozione manuale e non idempotente della sola configurazione generica.
-- Eseguire come postgres con psql -X -v ON_ERROR_STOP=1, dopo backup.
-- Nessuna riga di configurazione viene eliminata: una tabella non vuota blocca tutto.
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog;
SELECT pg_catalog.pg_advisory_xact_lock(3607902026);

DO $remove_setting_guard$
BEGIN
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'La migrazione deve essere eseguita come postgres';
    END IF;
END;
$remove_setting_guard$;

-- Anche i writer SQL che non usano il lock applicativo devono fermarsi.
LOCK TABLE foundation.setting IN ACCESS EXCLUSIVE MODE;
LOCK TABLE foundation.permission, foundation.role_permission IN SHARE ROW EXCLUSIVE MODE;

DO $remove_setting$
DECLARE
    setting_count bigint;
    removed_grants bigint;
    removed_permissions bigint;
    old_check text;
    new_check text;
    removed_codes constant text[] := ARRAY[
        'settings.read', 'settings.create', 'settings.update', 'settings.delete'
    ];
BEGIN
    SELECT count(*) INTO setting_count FROM foundation.setting;
    IF setting_count <> 0 THEN
        RAISE EXCEPTION 'foundation.setting non vuota: migrazione annullata (% righe)', setting_count;
    END IF;

    -- Conservare la definizione corrente degli altri permessi, anche di dominio.
    SELECT pg_catalog.pg_get_constraintdef(oid) INTO old_check
    FROM pg_catalog.pg_constraint
    WHERE conrelid = 'foundation.permission'::regclass
      AND conname = 'permission_system_code_check' AND contype = 'c' AND convalidated;
    IF old_check IS NULL OR position('''settings''::text, ' IN old_check) = 0 THEN
        RAISE EXCEPTION 'Vincolo catalogo permessi inatteso: migrazione annullata';
    END IF;
    new_check := replace(old_check, '''settings''::text, ', '');

    -- Le dipendenze esterne inattese bloccano la transazione, senza cancellarle.
    DROP TABLE foundation.setting RESTRICT;

    DELETE FROM foundation.role_permission rp
    USING foundation.permission p
    WHERE rp.tenant_id = p.tenant_id AND rp.permission_id = p.id
      AND p.code = ANY(removed_codes);
    GET DIAGNOSTICS removed_grants = ROW_COUNT;
    DELETE FROM foundation.permission WHERE code = ANY(removed_codes);
    GET DIAGNOSTICS removed_permissions = ROW_COUNT;

    ALTER TABLE foundation.permission DROP CONSTRAINT permission_system_code_check;
    EXECUTE 'ALTER TABLE foundation.permission ADD CONSTRAINT permission_system_code_check ' || new_check;

    INSERT INTO foundation.audit_event(action, resource, details)
    VALUES ('schema_migration', 'foundation.setting', jsonb_build_object(
        'settingRows', setting_count,
        'removedRolePermissions', removed_grants,
        'removedPermissions', removed_permissions
    ));
END;
$remove_setting$;
COMMIT;
