using System.Text.Json;
using Enginia360.Modules.TaxManagement;

namespace Enginia360.Verification.TaxManagement;

public static class TaxDeterminationSelfTests
{
    public static void Run()
    {
        var assertions = 0;
        var generated = 0;
        void Check(bool condition, string label)
        {
            if (!condition) throw new Exception("Tax determination: " + label);
            assertions++;
        }
        static Guid Id(int number) => Guid.Parse($"00000000-0000-0000-0000-{number:000000000000}");
        static JsonElement J<T>(T value) => JsonSerializer.SerializeToElement(value);
        var tenant = Id(1); var company = Id(2); var italy = Id(3); var type = Id(4); var codeId = Id(5);
        var date = new DateOnly(2026, 11, 26);
        var serial = 100;
        TaxRuleCondition Condition(string field, string op, object? value) => new(Id(serial++), field, op, J(value));
        TaxRuleVersion Version(params TaxRuleCondition[] conditions) =>
            new(Id(serial++), 1, codeId, 100, "SALE", "PUBLISHED", "Riferimento configurato", date, null, conditions);
        TaxRuleCandidate Candidate(TaxRuleVersion version, Guid? scope = null) => new(Id(serial++), "RULE", 7, scope, version);
        TaxRuleSnapshot Root(TaxRuleVersion version) => new(Id(10), tenant, null, italy, type, "RULE", 7, [version]);
        IReadOnlyList<TaxRuleIssue> Validate(TaxRuleVersion version) => TaxRuleValidator.Validate(Root(version), version);
        Dictionary<string, JsonElement?> Fields() => new(StringComparer.Ordinal)
        {
            ["company.establishmentCountry"] = J(italy), ["company.registrationCountry"] = J(italy),
            ["company.taxRegime"] = J(Id(6)), ["partner.establishmentCountry"] = J(italy),
            ["partner.actingAsTaxablePerson"] = J(true), ["transaction.ordinaryVatTerritoryConfirmed"] = J(true),
            ["transaction.specialTaxTreatment"] = J("NONE"), ["transaction.operationCategory"] = J("ORDINARY_MOVABLE_GOODS"),
            ["transaction.goodsCustomsStatus"] = J("NATIONAL_OR_UNION"), ["transaction.goodsLocationCountry"] = J(italy),
            ["transaction.dispatchCountry"] = J(italy), ["transaction.destinationCountry"] = J(italy),
            ["transaction.serviceLocationCountry"] = J(italy), ["item.taxClassification"] = J(Id(7)),
            ["partner.taxClassification"] = J(Id(8))
        };
        var context = new TaxDeterminationContext
        {
            TenantId = tenant, CompanyId = company, BusinessPartnerId = Id(9), ItemId = Id(11), TaxTypeId = type,
            ItalyCountryId = italy, TaxDate = date, OperationType = "SALE", TaxTypeCode = "VAT", ItemKind = "GOOD",
            CompanyRegimeCode = "ORDINARY", CompanyTaxRegistrationId = Id(12), Fields = Fields(),
            Snapshot = J(new { itemVersion = 4, partnerVersion = 6, itemTaxProfileId = Id(13), itemStreamRevision = 8 })
        };
        Dictionary<Guid, DeterminationTaxCode> Codes(params TaxFiscalVersion[] fiscal) => new()
        {
            [codeId] = new(italy, type, "VAT_STANDARD", new TaxCode(codeId, tenant, 9, true, true,
                fiscal.Length == 0 ? [new(Id(14), 22m, "TAXABLE", null, null, date, null)] : fiscal))
        };
        TaxDeterminationOutcome Determine(TaxDeterminationContext ctx, TaxRuleCandidate[] rules,
            Dictionary<Guid, DeterminationTaxCode>? codes = null, bool simulation = false) =>
            TaxDeterminationEngine.Determine(ctx, rules, codes ?? Codes(), simulation);
        TaxDeterminationContext Change(string key, JsonElement? value)
        {
            var fields = Fields(); fields[key] = value; return context with { Fields = fields };
        }

        // Whitelist, riferimenti tipizzati e forma stretta dei valori.
        Check(TaxConditionFields.All.Count == 20 && TaxConditionFields.All.Select(x => x.Key).Distinct().Count() == 20, "metadati finiti univoci");
        Check(TaxConditionFields.Find("partner.vatValidationStatus")?.Available == false, "VIES indisponibile");
        Check(Validate(Version()).Count == 0, "AND vuoto valido");
        foreach (var field in TaxConditionFields.All)
        {
            object value = field.Type == "REFERENCE" ? Id(30) : field.Type == "BOOLEAN" ? true : field.Values[0];
            var issues = Validate(Version(Condition(field.Key, "EQUALS", value)));
            Check(field.Available ? issues.Count == 0 : issues.Any(x => x.Code == "tax_rule_field_unavailable"), "tipo metadato " + field.Key);
        }
        foreach (var malformed in new[]
        {
            Condition("item.taxClassification", "EQUALS", "non-uuid"),
            Condition("item.taxClassification", "EQUALS", " " + Id(30).ToString("D") + " "),
            Condition("item.taxClassification", "EQUALS", Guid.Empty),
            Condition("item.taxClassification", "EQUALS", true),
            Condition("item.nature", "EQUALS", "GOODS"),
            Condition("partner.actingAsTaxablePerson", "EQUALS", "true"),
            Condition("partner.actingAsTaxablePerson", "IS_TRUE", true),
            Condition("item.nature", "IN", Array.Empty<string>()),
            Condition("item.nature", "IN", new[] { "GOOD", "GOOD" }),
            Condition("item.nature", "IN", new object[] { "GOOD", false }),
            Condition("item.nature", "IN", Enumerable.Repeat("GOOD", 101).ToArray())
        }) Check(Validate(Version(malformed)).Any(x => x.Code == "tax_rule_invalid_value"), "valore rifiutato " + malformed.Operator);
        Check(Validate(Version(Condition("unknown.path", "EQUALS", "x"))).Any(x => x.Code == "tax_rule_unknown_field"), "nessun percorso libero");
        Check(Validate(Version(Condition("item.nature", "CONTAINS", "GOOD"))).Any(x => x.Code == "tax_rule_invalid_operator"), "nessun operatore libero");
        Check(Validate(Version(Condition("partner.actingAsTaxablePerson", "IN", new[] { true }))).Any(x => x.Code == "tax_rule_invalid_operator"), "boolean IN vietato");
        var duplicate = Condition("item.nature", "IN", new[] { "GOOD", "SERVICE" });
        Check(Validate(Version(duplicate, Condition("item.nature", "IN", new[] { "SERVICE", "GOOD" }))).Any(x => x.Code == "tax_rule_duplicate_condition"), "duplicato insieme indipendente ordine");
        var structuralReference = Version(Condition("item.taxClassification", "EQUALS", Id(999)));
        Check(Validate(structuralReference).Count == 0, "esistenza riferimento delegata ad application");
        var basic = Version();
        Check(Validate(basic with { ValidTo = date.AddDays(-1) }).Any(x => x.Code == "tax_rule_invalid_interval"), "intervallo invertito");
        Check(Validate(basic with { LegalReference = " " }).Any(x => x.Code == "tax_rule_invalid_legal_reference"), "riferimento obbligatorio");
        Check(Validate(basic with { OperationType = "OTHER" }).Any(x => x.Code == "tax_rule_invalid_operation"), "operazione finita");
        Check(Validate(basic with { Conditions = Enumerable.Range(0, 101).Select(_ => Condition("item.nature", "EQUALS", "GOOD")).ToArray() }).Any(x => x.Code == "tax_rule_too_many_conditions"), "massimo cento");

        // Gli sconosciuti non diventano veri sotto negazione; la falsità prevale nell'AND.
        foreach (var op in new[] { "EQUALS", "NOT_EQUALS", "IN", "NOT_IN" })
        {
            var condition = Condition("item.nature", op, op is "IN" or "NOT_IN" ? new[] { "GOOD" } : "GOOD");
            foreach (var unknown in new JsonElement?[] { null, J<object?>(null), default(JsonElement), J(1), J("INVALID") })
                Check(TaxRuleMatcher.Match(Version(condition), new Dictionary<string, JsonElement?> { [condition.Field] = unknown }).Result == "UNKNOWN", "tri-state " + op);
        }
        foreach (var op in new[] { "EQUALS", "NOT_EQUALS", "IS_TRUE", "IS_FALSE" })
        {
            var condition = Condition("partner.actingAsTaxablePerson", op, op.StartsWith("IS_", StringComparison.Ordinal) ? null : true);
            Check(TaxRuleMatcher.Match(Version(condition), new Dictionary<string, JsonElement?>()).Result == "UNKNOWN", "boolean sconosciuto " + op);
        }
        Check(TaxRuleMatcher.Match(Version(Condition("item.nature", "EQUALS", "GOOD"), Condition("partner.actingAsTaxablePerson", "IS_TRUE", null)),
            new Dictionary<string, JsonElement?> { ["item.nature"] = J("SERVICE") }).Result == "NO_MATCH", "AND false vince");
        Check(TaxRuleMatcher.Match(Version(), new Dictionary<string, JsonElement?>()).Result == "MATCH", "AND vuoto vero");
        Check(TaxRuleMatcher.Match(Version(Condition("partner.vatValidationStatus", "EQUALS", "VALID")),
            new Dictionary<string, JsonElement?> { ["partner.vatValidationStatus"] = J("VALID") }).Result == "UNKNOWN", "nessun VIES inventato");

        // Oracolo esaustivo limitato: confronta intersezioni con enumerazione dei valori concreti.
        foreach (var spec in new[]
        {
            (Field: "item.nature", Atoms: new object[] { "GOOD", "SERVICE", "INTANGIBLE", "CHARGE" }, Reference: false),
            (Field: "company.taxRegime", Atoms: new object[] { Id(40), Id(41), Id(42), Id(43) }, Reference: true),
            (Field: "partner.actingAsTaxablePerson", Atoms: new object[] { true, false }, Reference: false)
        })
        {
            var conditions = new List<TaxRuleCondition>();
            var atoms = spec.Reference ? spec.Atoms.Take(3).ToArray() : spec.Atoms;
            foreach (var atom in atoms)
                foreach (var op in new[] { "EQUALS", "NOT_EQUALS" }) conditions.Add(Condition(spec.Field, op, atom));
            if (spec.Field == "partner.actingAsTaxablePerson")
            {
                conditions.Add(Condition(spec.Field, "IS_TRUE", null)); conditions.Add(Condition(spec.Field, "IS_FALSE", null));
            }
            else
            {
                for (var mask = 1; mask < 1 << atoms.Length; mask++)
                {
                    var values = atoms.Where((_, i) => (mask & 1 << i) != 0).ToArray();
                    conditions.Add(Condition(spec.Field, "IN", values)); conditions.Add(Condition(spec.Field, "NOT_IN", values));
                }
            }
            foreach (var leftCondition in conditions)
            foreach (var rightCondition in conditions)
            {
                var left = Candidate(Version(leftCondition)); var right = Candidate(Version(rightCondition));
                bool Matches(TaxRuleVersion version, object atom) => TaxRuleMatcher.Match(version,
                    new Dictionary<string, JsonElement?> { [spec.Field] = J(atom) }).Result == "MATCH";
                var expected = spec.Atoms.Any(atom => Matches(left.Version, atom) && Matches(right.Version, atom));
                Check(TaxRuleConflictDetector.Overlaps(left, right) == expected, "intersezione generata " + spec.Field);
                Check(TaxRuleConflictDetector.Overlaps(right, left) == expected, "simmetria generata " + spec.Field);
                var combined = Version(leftCondition, rightCondition with { Id = Id(serial++) });
                Check(Validate(combined).Any(x => x.Code == "tax_rule_contradictory_conditions") == !expected, "contraddizione generata " + spec.Field);
                generated++;
            }
        }
        // Due campi non correlati non autorizzano inferenze geografiche.
        var ca = Candidate(Version(Condition("transaction.dispatchCountry", "EQUALS", italy)));
        var cb = Candidate(Version(Condition("transaction.destinationCountry", "NOT_EQUALS", italy)));
        Check(TaxRuleConflictDetector.Overlaps(ca, cb), "nessuna correlazione inventata");
        Check(TaxRuleConflictDetector.Overlaps(ca, cb with { CompanyId = company }), "scope condiviso interseca company");
        Check(!TaxRuleConflictDetector.Overlaps(ca with { CompanyId = company }, cb with { CompanyId = Id(50) }), "company disgiunte");
        Check(!TaxRuleConflictDetector.Overlaps(ca, cb with { Version = cb.Version with { Priority = 101 } }), "priorita diverse non conflitto");
        Check(!TaxRuleConflictDetector.Overlaps(ca, cb with { Version = cb.Version with { OperationType = "PURCHASE" } }), "operazioni disgiunte");
        Check(TaxRuleConflictDetector.Overlaps(ca with { Version = ca.Version with { ValidTo = date } }, cb), "estremi inclusivi conflitto");
        Check(!TaxRuleConflictDetector.Overlaps(ca with { Version = ca.Version with { ValidTo = date } }, cb with { Version = cb.Version with { ValidFrom = date.AddDays(1) } }), "date disgiunte");
        var andLeft = Candidate(Version(Condition("item.nature", "IN", new[] { "GOOD", "SERVICE" }), Condition("item.nature", "NOT_EQUALS", "SERVICE")));
        var andRight = Candidate(Version(Condition("item.nature", "EQUALS", "SERVICE")));
        Check(!TaxRuleConflictDetector.Overlaps(andLeft, andRight), "intersezione AND non solo prima condizione");

        // Fatti territoriali espliciti, data tecnica minima e successione dei riferimenti legali.
        Check(TaxTerritorialityResolver.Resolve(context).Outcome == "SUCCESS", "beni ordinari IT");
        Check(TaxTerritorialityResolver.Resolve(context with { ItalyCountryId = Guid.Empty }).Outcome == "INCOMPLETE_CONTEXT", "identita Italia assente non prova estero");
        Check(TaxTerritorialityResolver.Resolve(Change("transaction.dispatchCountry", J(" " + italy.ToString("D") + " "))).Outcome == "INCOMPLETE_CONTEXT", "UUID fatto malformato non normalizzato");
        Check(TaxTerritorialityResolver.Resolve(context with { TaxDate = date.AddDays(-1) }).Outcome == "UNSUPPORTED_OPERATION", "limite tecnico inferiore");
        foreach (var key in new[] { "company.establishmentCountry", "company.registrationCountry", "partner.establishmentCountry", "partner.actingAsTaxablePerson",
            "transaction.ordinaryVatTerritoryConfirmed", "transaction.specialTaxTreatment", "transaction.operationCategory", "transaction.goodsCustomsStatus",
            "transaction.goodsLocationCountry", "transaction.dispatchCountry", "transaction.destinationCountry" })
        {
            var resolved = TaxTerritorialityResolver.Resolve(Change(key, null));
            Check(resolved.Outcome == "INCOMPLETE_CONTEXT" && resolved.MissingFields.Contains(key), "fatto necessario " + key);
        }
        foreach (var key in new[] { "company.establishmentCountry", "company.registrationCountry", "partner.establishmentCountry", "transaction.goodsLocationCountry", "transaction.dispatchCountry", "transaction.destinationCountry" })
            Check(TaxTerritorialityResolver.Resolve(Change(key, J(Id(60)))).Outcome == "UNSUPPORTED_OPERATION", "esterno positivo " + key);
        foreach (var key in new[] { "transaction.specialTaxTreatment", "transaction.goodsCustomsStatus" })
            Check(TaxTerritorialityResolver.Resolve(Change(key, J("OTHER"))).Outcome == "UNSUPPORTED_OPERATION", "specialita esclusa " + key);
        Check(TaxTerritorialityResolver.Resolve(Change("transaction.ordinaryVatTerritoryConfirmed", J(false))).Outcome == "UNSUPPORTED_OPERATION", "territorio speciale escluso");
        Check(TaxTerritorialityResolver.Resolve(Change("partner.actingAsTaxablePerson", J(false))).Outcome == "SUCCESS", "vendita ruolo privato esplicito supportato");
        Check(TaxTerritorialityResolver.Resolve(Change("partner.actingAsTaxablePerson", J(false)) with { OperationType = "PURCHASE" }).Outcome == "UNSUPPORTED_OPERATION", "acquisto da privato escluso");
        foreach (var kind in new[] { "INTANGIBLE", "CHARGE", "GOODS" })
            Check(TaxTerritorialityResolver.Resolve(context with { ItemKind = kind }).Outcome == "UNSUPPORTED_OPERATION", "kind reale richiesto " + kind);
        var serviceFields = Fields(); serviceFields["transaction.operationCategory"] = J("GENERAL_SERVICES");
        serviceFields.Remove("transaction.goodsLocationCountry"); serviceFields.Remove("transaction.goodsCustomsStatus");
        serviceFields.Remove("transaction.dispatchCountry"); serviceFields.Remove("transaction.destinationCountry");
        var service = context with { ItemKind = "SERVICE", Fields = serviceFields };
        Check(TaxTerritorialityResolver.Resolve(service).Outcome == "SUCCESS", "servizio generico non necessita fatti beni");
        Check(TaxTerritorialityResolver.Resolve(context with { ItemKind = "SERVICE" }).Outcome == "UNSUPPORTED_OPERATION", "categoria incoerente");
        foreach (var role in new[] { true, false })
        {
            var sf = new Dictionary<string, JsonElement?>(serviceFields) { ["partner.actingAsTaxablePerson"] = J(role) };
            Check(TaxTerritorialityResolver.Resolve(service with { Fields = sf }).Outcome == "SUCCESS", "servizi B2B/B2C");
        }
        foreach (var (ctx, oldArticle, newArticle) in new[] { (context, "7-bis", "15"), (service, "7-ter", "17") })
        {
            var before = TaxTerritorialityResolver.Resolve(ctx with { TaxDate = new(2026, 12, 31) });
            var after = TaxTerritorialityResolver.Resolve(ctx with { TaxDate = new(2027, 1, 1) });
            Check(before.LegalReference == "DPR 633/1972, art. " + oldArticle, "riferimento precedente inclusivo");
            Check(after.LegalReference == "TU allegato al D.Lgs. 10/2026, art. " + newArticle, "riferimento TU decorrenza inclusiva");
            Check(TaxTerritorialityResolver.Resolve(ctx with { TaxDate = DateOnly.MaxValue }).LegalReference == after.LegalReference, "nessun clock limite superiore");
        }

        // Selezione, bozze esplicite e nessuna precedenza Company implicita.
        var winner = Candidate(Version());
        var success = Determine(context, [winner]);
        Check(success.Outcome == "SUCCESS" && success.Result?.Rate == "22.000000", "risultato operativo");
        Check(success.Result is { Treatment: "TAXABLE", TaxNatureCode: null, LiableParty: "SUPPLIER", CollectionMechanism: "STANDARD" }, "output iniziale limitato");
        Check(success.Trace.TaxCodeRevision == 9 && success.Trace.Candidates.Single().RuleRevision == 7, "revisioni sorgenti nella traccia");
        Check(success.Trace.SourceSnapshot.GetProperty("itemStreamRevision").GetInt32() == 8, "stream profili nella traccia");
        Check(!success.IsSimulation && Determine(context, [winner], simulation: true).IsSimulation, "marcatore simulazione");
        Check(Determine(context, []).Outcome == "NO_MATCHING_RULE", "nessuna regola");
        var tie = Candidate(Version(), company);
        Check(Determine(context, [winner, tie]).Outcome == "AMBIGUOUS_RULE", "company non prevale sulla condivisa");
        var higher = Candidate(Version(Condition("partner.taxIdentifierCountry", "NOT_EQUALS", Id(60))) with { Priority = 200 });
        Check(Determine(context, [winner, higher]).Outcome == "INCOMPLETE_CONTEXT", "sconosciuto superiore blocca");
        Check(Determine(context, [winner, higher with { Version = higher.Version with { Priority = 100 } }]).Outcome == "INCOMPLETE_CONTEXT", "sconosciuto pari blocca");
        Check(Determine(context, [winner, higher with { Version = higher.Version with { Priority = 99 } }]).Outcome == "SUCCESS", "sconosciuto inferiore non blocca");
        var falseHigher = higher with { Version = higher.Version with { Conditions = [Condition("item.nature", "EQUALS", "SERVICE"), Condition("partner.taxIdentifierCountry", "NOT_EQUALS", italy)] } };
        Check(Determine(context, [winner, falseHigher]).Outcome == "SUCCESS", "false superiore vince su proprio unknown");
        foreach (var key in new[] { "item.taxClassification", "partner.taxClassification", "company.taxRegime" })
        {
            var incomplete = Determine(Change(key, null), [winner]);
            Check(incomplete.Outcome == "INCOMPLETE_CONTEXT" && incomplete.Trace.MissingFields.Contains(key), "profilo mancante esplicito " + key);
        }
        Check(Determine(context with { CompanyTaxRegistrationId = null }, [winner]).Outcome == "INCOMPLETE_CONTEXT", "nessuna registrazione implicita");
        Check(Determine(context, [winner with { CompanyId = Id(60) }]).Outcome == "NO_MATCHING_RULE", "company diversa esclusa");
        Check(Determine(context, [winner with { Version = winner.Version with { Status = "WITHDRAWN" } }]).Outcome == "NO_MATCHING_RULE", "ritirata anche retrodata esclusa");
        Check(Determine(context, [winner with { Version = winner.Version with { ValidTo = date } }]).Outcome == "SUCCESS", "data fine inclusiva");
        Check(Determine(context with { TaxDate = date.AddDays(1) }, [winner with { Version = winner.Version with { ValidTo = date } }]).Outcome == "NO_MATCHING_RULE", "dopo fine esclusa");
        var draft = winner with { Version = Version(Condition("item.nature", "EQUALS", "SERVICE")) with { Status = "DRAFT" } };
        Check(Determine(context, [winner, draft]).Outcome == "SUCCESS", "bozza ignorata determinazione");
        Check(Determine(context, [winner, draft], simulation: true).Outcome == "NO_MATCHING_RULE", "bozza sostituisce solo propria radice");
        Check(Determine(context, [winner, draft, tie], simulation: true).Result?.TaxRuleId == tie.RuleId, "altre pubblicate conservate preview");

        // Risoluzione dinamica del codice alla data: nessun fallback su lacuna o output non supportato.
        var oldFiscal = new TaxFiscalVersion(Id(70), 19m, "TAXABLE", null, "Vecchio", date, new(2026, 12, 31));
        var futureFiscal = new TaxFiscalVersion(Id(71), 23.125m, "TAXABLE", null, "Nuovo", new(2027, 1, 1), null);
        var scheduled = Codes(oldFiscal, futureFiscal);
        Check(Determine(context with { TaxDate = new(2026, 12, 31) }, [winner], scheduled).Result?.Rate == "19.000000", "ultima data aliquota precedente");
        var changedRate = Determine(context with { TaxDate = new(2027, 1, 1) }, [winner], scheduled);
        Check(changedRate.Result?.Rate == "23.125000" && changedRate.Result.TaxCodeVersionId == Id(71), "prima data aliquota futura senza percentuale regola");
        Check(changedRate.Trace.TaxCodeRevision == 9 && changedRate.Trace.TaxCodeVersionId == Id(71), "versione codice effettiva tracciata");
        var gap = Codes(oldFiscal with { ValidTo = date }, futureFiscal);
        var alternateCodeId = Id(82);
        var lower = Candidate(Version() with { Priority = 10, TaxCodeId = alternateCodeId });
        gap[alternateCodeId] = new(italy, type, "ALTERNATE", new TaxCode(alternateCodeId, tenant, 3, true, true,
            [new(Id(83), 11m, "TAXABLE", null, null, date, null)]));
        Check(Determine(context with { TaxDate = date.AddDays(1) }, [lower], gap).Outcome == "SUCCESS", "controllo regola inferiore utilizzabile");
        Check(Determine(context with { TaxDate = date.AddDays(1) }, [winner, lower], gap).Outcome == "TAX_CODE_UNAVAILABLE", "lacuna codice non ripiega regola inferiore");
        Check(Determine(context, [winner], new()).Outcome == "TAX_CODE_UNAVAILABLE", "codice assente");
        foreach (var altered in new[]
        {
            new DeterminationTaxCode(italy, type, "X", new TaxCode(codeId, tenant, 9, false, true, [oldFiscal])),
            new DeterminationTaxCode(italy, type, "X", new TaxCode(codeId, tenant, 9, true, false, [oldFiscal])),
            new DeterminationTaxCode(italy, type, "X", new TaxCode(codeId, Id(80), 9, true, true, [oldFiscal])),
            new DeterminationTaxCode(Id(80), type, "X", new TaxCode(codeId, tenant, 9, true, true, [oldFiscal])),
            new DeterminationTaxCode(italy, Id(80), "X", new TaxCode(codeId, tenant, 9, true, true, [oldFiscal]))
        }) Check(Determine(context, [winner], new() { [codeId] = altered }).Outcome == "TAX_CODE_UNAVAILABLE", "codice non utilizzabile/ambito");
        foreach (var fiscal in new[] { oldFiscal with { Treatment = "EXEMPT", Rate = 0 }, oldFiscal with { Rate = 0 }, oldFiscal with { TaxNatureCodeId = Id(81) } })
            Check(Determine(context, [winner], Codes(fiscal)).Outcome == "UNSUPPORTED_OPERATION", "output fuori perimetro rifiutato");
        var orderA = Determine(context, [winner, higher, tie]);
        var orderB = Determine(context, [tie, higher, winner]);
        Check(JsonSerializer.Serialize(orderA) == JsonSerializer.Serialize(orderB), "traccia deterministica candidati permutati");
        Check(orderA.Trace.Candidates.Select(x => x.RuleId).SequenceEqual(orderB.Trace.Candidates.Select(x => x.RuleId)), "ordine stabile identificativi");
        Check(!JsonSerializer.Serialize(success.Trace).Contains("vatNumber", StringComparison.OrdinalIgnoreCase), "nessuna PII sintetizzata");
        Console.WriteLine($"Tax determination self-tests passed: {assertions} assertions; {generated} generated condition intersections.");
    }
}
