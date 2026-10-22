using System.Security.Claims;
using Enginia360.Api.BrowserAuthentication;
using Microsoft.AspNetCore.Authentication;
using Xunit;

public sealed class BoundedTicketStoreTests
{
    private sealed class Clock : TimeProvider
    {
        // Whole seconds only: the framework ticket serializer stores second precision.
        internal DateTimeOffset Now = new(DateTimeOffset.UtcNow.UtcDateTime.Ticks
            / TimeSpan.TicksPerSecond * TimeSpan.TicksPerSecond, TimeSpan.Zero);
        public override DateTimeOffset GetUtcNow() => Now;
    }

    private static AuthenticationTicket Ticket(DateTimeOffset expires) => new(
        new(new ClaimsIdentity([new(ClaimTypes.NameIdentifier, Guid.NewGuid().ToString("D"))], "browser")),
        new() { ExpiresUtc = expires, IsPersistent = true }, "browser");

    [Fact]
    public async Task Absolute_expiry_is_capped_and_reads_and_renewal_never_slide_it()
    {
        var clock = new Clock();
        var store = new BoundedTicketStore(clock);
        var key = await store.StoreAsync(Ticket(clock.Now.AddDays(1)));
        var stored = (await store.RetrieveAsync(key))!;
        Assert.Equal(clock.Now.AddMinutes(15), stored.Properties.ExpiresUtc);
        Assert.False(stored.Properties.IsPersistent);
        clock.Now = clock.Now.AddMinutes(14);
        await store.RenewAsync(key, Ticket(clock.Now.AddDays(1)));
        Assert.NotNull(await store.RetrieveAsync(key));
        clock.Now = clock.Now.AddMinutes(1);
        Assert.Null(await store.RetrieveAsync(key));
    }

    [Fact]
    public async Task Store_capacity_is_bounded_and_expired_entries_release_capacity()
    {
        var clock = new Clock();
        var store = new BoundedTicketStore(clock);
        for (var index = 0; index < BoundedTicketStore.Capacity; index++)
            await store.StoreAsync(Ticket(clock.Now.AddMinutes(15)));
        await Assert.ThrowsAsync<InvalidOperationException>(() => store.StoreAsync(Ticket(clock.Now.AddMinutes(15))));
        clock.Now = clock.Now.AddMinutes(15);
        Assert.NotNull(await store.StoreAsync(Ticket(clock.Now.AddMinutes(15))));
    }

    [Fact]
    public async Task Concurrent_remove_and_renew_cannot_resurrect_a_revoked_ticket()
    {
        var clock = new Clock();
        var store = new BoundedTicketStore(clock);
        for (var index = 0; index < 100; index++)
        {
            var ticket = Ticket(clock.Now.AddMinutes(15));
            var key = await store.StoreAsync(ticket);
            await Task.WhenAll(Task.Run(() => store.RemoveAsync(key)), Task.Run(() => store.RenewAsync(key, ticket)));
            Assert.Null(await store.RetrieveAsync(key));
        }
    }

    [Fact]
    public async Task Tickets_are_copied_and_new_login_keys_are_distinct()
    {
        var clock = new Clock();
        var store = new BoundedTicketStore(clock);
        var ticket = Ticket(clock.Now.AddMinutes(15));
        var key = await store.StoreAsync(ticket);
        ticket.Properties.Items["mutated"] = "true";
        var copy = (await store.RetrieveAsync(key))!;
        Assert.False(copy.Properties.Items.ContainsKey("mutated"));
        copy.Properties.Items["mutated"] = "true";
        Assert.False((await store.RetrieveAsync(key))!.Properties.Items.ContainsKey("mutated"));
        Assert.NotEqual(key, await store.StoreAsync(ticket));
    }
}
