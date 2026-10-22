using Microsoft.IdentityModel.Protocols;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;

namespace Enginia360.Api.BrowserAuthentication;

// Keep the official discovery/JWKS retriever, refresh policy and signature validation.
// Fail before any authorization/PAR/token exchange if trusted metadata changes the transport boundary.
public sealed class HttpsOidcConfigurationManager(
    IConfigurationManager<OpenIdConnectConfiguration> inner,
    string issuer
) : IConfigurationManager<OpenIdConnectConfiguration>
{
    public async Task<OpenIdConnectConfiguration> GetConfigurationAsync(CancellationToken cancellationToken)
    {
        var configuration = await inner.GetConfigurationAsync(cancellationToken);
        if (configuration.Issuer != issuer
            || !IsHttps(configuration.AuthorizationEndpoint)
            || !IsHttps(configuration.TokenEndpoint)
            || !IsHttps(configuration.JwksUri)
            || (!string.IsNullOrEmpty(configuration.PushedAuthorizationRequestEndpoint)
                && !IsHttps(configuration.PushedAuthorizationRequestEndpoint)))
            throw new BrowserIdentityConfigurationException();
        return configuration;
    }

    private static bool IsHttps(string? value) =>
        Uri.TryCreate(value, UriKind.Absolute, out var uri)
        && uri.Scheme == "https" && uri.UserInfo.Length == 0 && uri.Fragment.Length == 0;

    public void RequestRefresh() => inner.RequestRefresh();
}

public sealed class BrowserIdentityConfigurationException : Exception
{
    public BrowserIdentityConfigurationException() : base("Identity provider configuration is unavailable or invalid.") { }
}
