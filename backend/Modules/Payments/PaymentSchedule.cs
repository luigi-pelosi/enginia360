namespace Enginia360.Modules.Payments;

public enum DueDateMode { Exact, EndOfMonth, FixedDay }
public sealed record PaymentInstallment(decimal Percentage, int Months, int Days, bool ReferenceMonthEnd, DueDateMode Mode, int? FixedDay, string? Method);
public sealed record PaymentDue(DateOnly DueDate, decimal Amount, string? Method);

public static class PaymentSchedule
{
    public static IReadOnlyList<PaymentDue> Calculate(DateOnly referenceDate, decimal total, int precision, IReadOnlyList<PaymentInstallment> installments, string? defaultMethod)
    {
        ArgumentNullException.ThrowIfNull(installments);
        if (precision is < 0 or > 28) throw new ArgumentOutOfRangeException(nameof(precision));
        if (total < 0 || decimal.Round(total, precision) != total) throw new ArgumentOutOfRangeException(nameof(total));
        if (installments.Count == 0 || installments.Any(x => x is null || x.Percentage <= 0 || x.Percentage > 100) || installments.Sum(x => x.Percentage) != 100m)
            throw new ArgumentException("Installment percentages must be positive and total 100.", nameof(installments));
        var result = new List<PaymentDue>(installments.Count);
        decimal allocated = 0;
        for (var i = 0; i < installments.Count; i++)
        {
            var row = installments[i];
            if (row.Months < 0 || row.Days < 0 || !Enum.IsDefined(row.Mode) || (row.Mode == DueDateMode.FixedDay && row.FixedDay is not (>= 1 and <= 31)) || (row.Mode != DueDateMode.FixedDay && row.FixedDay is not null))
                throw new ArgumentException("Invalid due date mode or fixed day.", nameof(installments));
            var date = row.ReferenceMonthEnd ? EndOfMonth(referenceDate) : referenceDate;
            date = date.AddMonths(row.Months).AddDays(row.Days);
            date = row.Mode switch {
                DueDateMode.EndOfMonth => EndOfMonth(date),
                DueDateMode.FixedDay => new DateOnly(date.Year, date.Month, Math.Min(row.FixedDay!.Value, DateTime.DaysInMonth(date.Year, date.Month))),
                _ => date
            };
            var amount = i == installments.Count - 1 ? total - allocated : Math.Min(total - allocated, decimal.Round(total * (row.Percentage / 100m), precision, MidpointRounding.AwayFromZero));
            allocated += amount;
            result.Add(new(date, amount, string.IsNullOrWhiteSpace(row.Method) ? defaultMethod : row.Method));
        }
        return result;
    }

    private static DateOnly EndOfMonth(DateOnly date) => new(date.Year, date.Month, DateTime.DaysInMonth(date.Year, date.Month));
}
