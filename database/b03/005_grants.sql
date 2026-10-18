GRANT SELECT ON organization_access.company_permissions TO :"app_user";
GRANT USAGE ON SCHEMA counterparties TO :"app_user";
GRANT SELECT ON counterparties.counterparties TO :"app_user";
