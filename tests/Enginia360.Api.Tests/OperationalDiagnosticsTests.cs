using System.Collections.Concurrent;
using System.Diagnostics.Metrics;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public sealed class OperationalDiagnosticsTests
{
    [Fact]
    public async Task Http_requests_emit_bounded_duration_metric_without_resource_or_identity_tags()
    {
        var measurements = new ConcurrentQueue<(double Value, string[] Tags)>();
        using var listener = new MeterListener();
        listener.InstrumentPublished = (instrument, current) =>
        {
            if (instrument.Meter.Name == "Enginia360.Api" && instrument.Name == "enginia360.http.duration")
                current.EnableMeasurementEvents(instrument);
        };
        listener.SetMeasurementEventCallback<double>((_, value, tags, _) =>
            measurements.Enqueue((value, tags.ToArray().Select(tag => tag.Key).ToArray())));
        listener.Start();
        await using var factory = new WebApplicationFactory<Program>();
        using var client = factory.CreateClient();
        await client.GetAsync("/api/v1/system/status?private=not-a-label");
        Assert.NotEmpty(measurements);
        Assert.All(measurements, sample =>
        {
            Assert.True(sample.Value >= 0);
            Assert.Equal(new[] { "http.request.method", "http.response.status_code" }, sample.Tags);
        });
    }
}
