namespace Enginia360.Shared.Validation;

public static class Check
{
    public static void Require(bool valid, int status = 400, string code = "validation_error")
    {
        if (!valid) throw new ApiException(status, code);
    }
    public static string Password(string? value)
    {
        Require(value is { Length: >= 14 and <= 256 } && !value.Contains('\0'));
        return value!;
    }
}
