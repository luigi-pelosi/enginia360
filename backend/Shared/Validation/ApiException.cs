namespace Enginia360.Shared.Validation;

public sealed class ApiException(int status, string code) : Exception(code)
{
    public int Status { get; } = status;
    public string Code { get; } = code;
}
