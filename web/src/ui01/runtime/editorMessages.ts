// Italian operator messages for the closed server error codes; unknown codes fall back to the generic ApiError text.
export const codeMessages: Record<string, string> = {
  revision_changed: 'La commessa è cambiata da un altro comando: rileggi prima di ripetere.',
  line_policy_changed: 'La policy righe è cambiata: rileggi.',
  structure_policy_changed: 'La struttura dell’editor è cambiata: rileggi.',
  line_policy_missing: 'Policy righe non configurata per questo tipo documento: nessuna scrittura possibile.',
  order_technically_closed: 'Commessa chiusa tecnicamente: sola lettura.',
  group_not_empty: 'La lavorazione contiene righe o note: nessuna cascata, rimuovile prima.',
  group_not_found: 'Lavorazione non disponibile.',
  line_not_found: 'Riga non disponibile.',
  no_change: 'Nessuna differenza da registrare.',
  material_structure_edit_not_supported: 'Modifica strutturale o rimozione dei ricambi non supportata in questo incremento: solo prezzo, sconto e descrizione.',
  commercial_summary_limit: 'Il totale supera il limite tecnico di importo: nessuna modifica registrata.',
  workspace_limit: 'Limite tecnico di righe, note o lavorazioni raggiunto.',
  multiple_groups_not_enabled: 'Il profilo documento ammette una sola lavorazione.',
  catalog_version_changed: 'La versione del catalogo è cambiata: aggiorna la ricerca.',
  catalog_item_not_found: 'Articolo o prestazione non disponibile.',
  revision_limit: 'Limite revisioni raggiunto.',
};
