using System.Runtime.CompilerServices;

internal static class TestEnvironment
{
    [ModuleInitializer]
    internal static void Initialize()
    {
        Environment.SetEnvironmentVariable(
            "ConnectionStrings__OrganizationAccess",
            "Host=127.0.0.1;Database=unused;Username=unused;Password=unused;Maximum Pool Size=1"
        );
        Environment.SetEnvironmentVariable(
            "Authentication__ValidIssuer",
            "https://issuer.test/real-config"
        );
        Environment.SetEnvironmentVariable("Authentication__Audience", "enginia360-api");
        Environment.SetEnvironmentVariable("Authentication__RequireHttpsMetadata", "false");
    }
}
