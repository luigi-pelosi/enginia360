using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Npgsql;
using NpgsqlTypes;

namespace Enginia360.Infrastructure.Persistence;

public sealed class AppDb(DbContextOptions<AppDb> options) : DbContext(options)
{
    public DbSet<User> Users => Set<User>();
    protected override void OnModelCreating(ModelBuilder model)
    {
        var a = model.Entity<User>();
        a.ToTable("user", "foundation");
        a.HasKey(x => x.Id);
        a.Property(x => x.FirstName).HasMaxLength(200).IsRequired();
        a.Property(x => x.LastName).HasMaxLength(200).IsRequired();
        a.Property(x => x.Email).HasMaxLength(254).IsRequired();
        a.Property(x => x.DateOfBirth).HasColumnType("date");
        a.Property(x => x.PhoneNumber).HasMaxLength(50);
        a.Property(x => x.PreferredLanguage).IsRequired().HasDefaultValue("it");
        foreach (var p in a.Metadata.GetProperties())
        {
            var name = System.Text.RegularExpressions.Regex.Replace(p.Name, "([a-z0-9])([A-Z])", "$1_$2").ToLowerInvariant();
            p.SetColumnName(name);
        }
    }

    public async Task<NpgsqlCommand> Command(string sql, params (string Name, object? Value)[] values)
    {
        await Database.OpenConnectionAsync();
        var cmd = new NpgsqlCommand(sql, (NpgsqlConnection)Database.GetDbConnection(),
            (NpgsqlTransaction?)Database.CurrentTransaction?.GetDbTransaction());
        cmd.CommandTimeout = 15;
        foreach (var (name, value) in values)
            cmd.Parameters.Add(new NpgsqlParameter(name, value ?? DBNull.Value));
        return cmd;
    }
    public async Task<int> Execute(string sql, params (string Name, object? Value)[] values)
    {
        await using var cmd = await Command(sql, values);
        return await cmd.ExecuteNonQueryAsync();
    }
    public async Task<object?> Scalar(string sql, params (string Name, object? Value)[] values)
    {
        await using var cmd = await Command(sql, values);
        return await cmd.ExecuteScalarAsync();
    }
    public Task<int> Audit(Guid? actor, Guid? tenant, string action, string resource, Guid? record, object? details = null)
    {
        string? json=null;
        if(details != null)
        {
            var value=System.Text.Json.JsonSerializer.SerializeToElement(details);
            Check.Require(value.ValueKind == System.Text.Json.JsonValueKind.Object);
            json=value.GetRawText();
        }
        return Execute(
            "INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES (@actor::uuid,@tenant::uuid,@action,@resource,@record::uuid,@details::jsonb)",
            ("actor", actor), ("tenant", tenant), ("action", action), ("resource", resource), ("record", record), ("details",json));
    }
}

