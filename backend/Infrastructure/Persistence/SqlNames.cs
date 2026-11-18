namespace Enginia360.Infrastructure.Persistence;

// Gli identificatori provengono dai metadati statici, mai dai valori delle richieste.
public static class SqlNames
{
    public static string Identifier(string name)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);
        if (name.Contains('\0')) throw new ArgumentException("Invalid SQL identifier.", nameof(name));
        return "\"" + name.Replace("\"", "\"\"") + "\"";
    }
    public static string Table(string name) => Identifier("foundation") + "." + Identifier(name);
}

