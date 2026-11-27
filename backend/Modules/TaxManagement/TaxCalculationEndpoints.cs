using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public static class TaxCalculationEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/tax/calculation-policy", Policy);
        app.MapPost("/api/tax/calculations/simulate",
            (HttpContext ctx, AppDb db, JsonElement body) => Calculate(ctx, db, body, true));
        app.MapPost("/api/tax/calculations",
            (HttpContext ctx, AppDb db, JsonElement body) => Calculate(ctx, db, body, false));
    }

    private static async Task<IResult> Policy(HttpContext ctx, AppDb db)
    {
        var (company, currency) = TaxCalculationInput.PolicyQuery(ctx);
        var tenant = await TaxRuleReferences.Tenant(ctx, db, "tax-calculation");
        await TaxRuleReferences.Action(ctx, db, tenant, company, "tax-calculation.read");
        await CompanyTaxApplication.Company(db, tenant, company, false);
        var resolved = await TaxCalculationPolicyResolver.Resolve(db, currency);
        var permissions = await TaxRuleReferences.Permissions(ctx, db, tenant, company, "tax-calculation");
        return Results.Ok(new { policy = resolved.Policy, currency = resolved.Currency, permissions });
    }

    private static async Task<IResult> Calculate(HttpContext ctx, AppDb db, JsonElement body, bool simulation)
    {
        TaxCalculationInputRequest input;
        try { input = TaxCalculationInput.Parse(body, simulation); }
        catch (InvalidOperationException) { throw new ApiException(400, "tax_invalid_payload"); }
        var tenant = await TaxRuleReferences.Tenant(ctx, db, "tax-calculation");
        var outcome = await TaxCalculationApplication.Calculate(ctx, db, tenant, input, simulation);
        if (outcome.FiscalFailure is { } failure)
            return Results.Json(new
            {
                code = "tax_calculation_determination_failed",
                field = "lines[" + outcome.FailedLineIndex + "].fiscal_context",
                outcome = failure.Outcome,
                trace = failure.Trace,
                isSimulation = simulation
            }, statusCode: 422);
        return Results.Ok(new { isSimulation = simulation, result = outcome.Result });
    }
}
