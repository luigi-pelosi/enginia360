using Enginia360.Modules.Payments;

namespace Enginia360.Verification.Payments;

public static class PaymentScheduleTests
{
    public static void Run(Action<string, Action> test)
    {
        test("payment schedule: percentages and residual", () => {
            var rows = PaymentSchedule.Calculate(new DateOnly(2024, 1, 15), 100m, 2,
                [new(33.33m, 0, 0, false, DueDateMode.Exact, null, null), new(33.33m, 1, 0, false, DueDateMode.Exact, null, "card"), new(33.34m, 2, 0, false, DueDateMode.Exact, null, null)], "bank");
            if (rows.Count != 3 || rows[0].Amount != 33.33m || rows[1].Amount != 33.33m || rows[2].Amount != 33.34m || rows[0].Method != "bank" || rows[1].Method != "card") throw new Exception("Incorrect amounts or methods");
        });
        test("payment schedule: small total cannot yield negative last installment", () => {
            var items = Enumerable.Range(0, 4).Select(_ => new PaymentInstallment(25m, 0, 0, false, DueDateMode.Exact, null, null)).ToArray();
            var rows = PaymentSchedule.Calculate(new DateOnly(2024, 1, 1), 0.02m, 2, items, null);
            if (rows.Any(x => x.Amount < 0) || rows.Sum(x => x.Amount) != 0.02m) throw new Exception("Negative installment or lost residual");
        });
        test("payment schedule: reference and due date rules", () => {
            var rows = PaymentSchedule.Calculate(new DateOnly(2024, 1, 15), 10m, 2,
                [new(25, 1, 2, false, DueDateMode.Exact, null, null),
                 new(25, 1, 0, true, DueDateMode.EndOfMonth, null, null),
                 new(25, 1, 0, false, DueDateMode.FixedDay, 31, null),
                 new(25, 0, 20, true, DueDateMode.Exact, null, " ")], "bank");
            var expected = new[] { new DateOnly(2024, 2, 17), new DateOnly(2024, 2, 29), new DateOnly(2024, 2, 29), new DateOnly(2024, 2, 20) };
            if (!rows.Select(x => x.DueDate).SequenceEqual(expected) || rows[3].Method != "bank") throw new Exception("Incorrect dates or fallback");
        });
        test("payment schedule: invalid inputs rejected", () => {
            var day = new DateOnly(2024, 1, 1);
            void Reject(Action action) { try { action(); } catch (ArgumentException) { return; } throw new Exception("Expected invalid argument"); }
            Reject(() => PaymentSchedule.Calculate(day, 10, 2, [], null));
            Reject(() => PaymentSchedule.Calculate(day, 10, 2, [new(99, 0, 0, false, DueDateMode.Exact, null, null)], null));
            Reject(() => PaymentSchedule.Calculate(day, 10, 2, [new(100, 0, 0, false, DueDateMode.FixedDay, 32, null)], null));
            Reject(() => PaymentSchedule.Calculate(day, 10.001m, 2, [new(100, 0, 0, false, DueDateMode.Exact, null, null)], null));
            Reject(() => PaymentSchedule.Calculate(day, 10, 29, [new(100, 0, 0, false, DueDateMode.Exact, null, null)], null));
            Reject(() => PaymentSchedule.Calculate(day, 10, 2, [new(100, -1, 0, false, DueDateMode.Exact, null, null)], null));
            Reject(() => PaymentSchedule.Calculate(day, 10, 2, [new(100, 0, -1, false, DueDateMode.Exact, null, null)], null));
        });
        test("payment schedule: rounding follows precision and final residual", () => {
            var rows = PaymentSchedule.Calculate(new DateOnly(2024, 1, 1), 1m, 2,
                [new(50, 0, 0, false, DueDateMode.Exact, null, null), new(50, 0, 0, false, DueDateMode.Exact, null, null)], null);
            if (rows[0].Amount != 0.50m || rows[1].Amount != 0.50m) throw new Exception("Unexpected rounding");
            rows = PaymentSchedule.Calculate(new DateOnly(2024, 1, 1), 0.05m, 2,
                [new(50, 0, 0, false, DueDateMode.Exact, null, null), new(50, 0, 0, false, DueDateMode.Exact, null, null)], null);
            if (rows[0].Amount != 0.03m || rows[1].Amount != 0.02m) throw new Exception("Unexpected midpoint or residual");
        });
    }
}
