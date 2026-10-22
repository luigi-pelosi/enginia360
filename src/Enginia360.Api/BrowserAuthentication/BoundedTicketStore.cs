using System.Security.Cryptography;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;

namespace Enginia360.Api.BrowserAuthentication;

// Single process only. A restart discards all tickets. No persisted keys or session fallback.
public sealed class BoundedTicketStore(TimeProvider clock) : ITicketStore
{
    public const int Capacity = 1024;
    public static readonly TimeSpan Lifetime = TimeSpan.FromMinutes(15);
    private readonly object gate = new();
    private readonly Dictionary<string, Entry> entries = new(StringComparer.Ordinal);
    private sealed record Entry(byte[] Ticket, DateTimeOffset Expires);

    public Task<string> StoreAsync(AuthenticationTicket ticket)
    {
        lock (gate)
        {
            var now = clock.GetUtcNow();
            foreach (var key in entries.Where(pair => pair.Value.Expires <= now).Select(pair => pair.Key).ToArray())
                entries.Remove(key);
            if (entries.Count >= Capacity)
                throw new InvalidOperationException("Session capacity reached.");
            var expires = ticket.Properties.ExpiresUtc is { } requested && requested < now + Lifetime
                ? requested : now + Lifetime;
            ticket.Properties.ExpiresUtc = expires;
            ticket.Properties.IsPersistent = false;
            var keyValue = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
            entries.Add(keyValue, new(TicketSerializer.Default.Serialize(ticket), expires));
            return Task.FromResult(keyValue);
        }
    }

    // Absolute sessions never slide. In particular an in-flight renewal cannot resurrect a removed ticket.
    public Task RenewAsync(string key, AuthenticationTicket ticket) => Task.CompletedTask;

    public Task<AuthenticationTicket?> RetrieveAsync(string key)
    {
        lock (gate)
        {
            if (entries.TryGetValue(key, out var entry))
            {
                if (entry.Expires > clock.GetUtcNow())
                    return Task.FromResult(TicketSerializer.Default.Deserialize(entry.Ticket));
                entries.Remove(key);
            }
            return Task.FromResult<AuthenticationTicket?>(null);
        }
    }

    public Task RemoveAsync(string key)
    {
        lock (gate)
            entries.Remove(key);
        return Task.CompletedTask;
    }
}
