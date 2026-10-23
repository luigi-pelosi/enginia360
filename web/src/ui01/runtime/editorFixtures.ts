export const id = '11111111-1111-4111-8111-111111111111';
export const order = { id, legalEntityId: id, siteId: id, documentTypeId: id, configurationVersion: 7, payerId: id, vehicleId: id, vehicleHolderId: '22222222-2222-4222-8222-222222222222', isCustomerOrder: true };
export const summary = { orderId: id, payerId: id, revision: 0, lines: [], netAmount: '0.000000', taxAmount: '0.000000', total: '0.000000', currency: 'EUR', policy: 'Case001' };
export const policy = { orderId: id, state: 'ready', documentTypeId: id, documentConfigurationVersion: 7, currentLinePolicyVersion: 9, calculationPolicy: 'Case001', multipleWorkingGroups: true, structurePolicyVersion: 1, limits: { maxActiveLines: 1000, maxActiveGroups: 100, maxActiveNotes: 1000, maxDescriptionLength: 500 }, supportedCommands: [] };
export const capabilities = { closed: false, canAddLine: true, canEditLine: true, canRemoveLine: true, canWriteNotes: true, canWriteGroups: true, materialStructureEdit: false, materialStructureEditReason: 'Modifica strutturale dei ricambi non supportata in questo incremento.' };
export const editorView = { order, revision: 0, linePolicy: policy, groups: [], rows: [], summary, capabilities };
