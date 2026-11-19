export const catalog = [
  ...["business-partners.read", "business-partners.create", "business-partners.update", "business-partner-numbering.read", "business-partner-numbering.update"].map(code => ({id: code, code})),
  ...["companies", "sites", "sales-organizations", "purchasing-organizations", "warehouse-types", "warehouses", "warehouse-locations", "settings", "users", "groups", "roles"].flatMap(resource => ["delete", "update", "create", "read"].map(action => ({id: `${resource}.${action}`, code: `${resource}.${action}`}))),
  ...["permissions.read", "users.reset_password", "roles.assign", "groups.assign_users", "roles.assign_permissions", "purchasing-organizations.assign_scope"].map(code => ({id: code, code})),
];
