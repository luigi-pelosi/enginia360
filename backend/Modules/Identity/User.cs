namespace Enginia360.Modules.Identity;

public sealed class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid? TenantId { get; set; }
    public string Email { get; set; } = "";
    public string Username { get; set; } = "";
    public string FirstName { get; set; } = "";
    public string LastName { get; set; } = "";
    public DateOnly? DateOfBirth { get; set; }
    public string? PhoneNumber { get; set; }
    public string PreferredLanguage { get; set; } = "it";
    [System.ComponentModel.DataAnnotations.Schema.NotMapped]
    public string FullName => $"{FirstName} {LastName}".Trim();
    public string? PasswordHash { get; set; }
    public Guid SecurityStamp { get; set; } = Guid.NewGuid();
    public bool IsSuperAdmin { get; set; }
    public bool IsEnabled { get; set; } = true;
    public bool MustChangePassword { get; set; } = true;
    public int FailedAttempts { get; set; }
    public DateTimeOffset? LockedUntil { get; set; }
}

