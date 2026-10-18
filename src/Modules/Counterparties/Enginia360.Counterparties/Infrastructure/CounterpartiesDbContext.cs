using Enginia360.Counterparties.Domain;
using Microsoft.EntityFrameworkCore;
namespace Enginia360.Counterparties.Infrastructure;
internal sealed class CounterpartiesDbContext(DbContextOptions<CounterpartiesDbContext> options) : DbContext(options)
{
    internal DbSet<Counterparty> Counterparties => Set<Counterparty>();
    internal DbSet<Destination> Destinations => Set<Destination>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Destination>().ToTable("destinations", "counterparties").HasKey(x => x.Id);
        b.Entity<Counterparty>().ToTable("counterparties", "counterparties").HasKey(x => x.Id);
    }
}
