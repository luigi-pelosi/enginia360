using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Numbering;
using Enginia360.Shared.Validation;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Verification.Catalog;

// Eseguito soltanto dal runner esplicito contro il PostgreSQL effimero del test Python.
public static class CatalogNumberingTests
{
    public static async Task Run(string connection)
    {
        AppDb Db()=>new(new DbContextOptionsBuilder<AppDb>().UseNpgsql(connection).Options);
        void Require(bool ok,string message) {if(!ok) throw new Exception(message);}
        var tenant=Guid.NewGuid();
        await using(var db=Db()) {
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@id,@code,'Kernel proof')",("id",tenant),("code",tenant.ToString()));
            await using var tx=await db.Database.BeginTransactionAsync();
            foreach(var entity in new[]{"BUSINESS_PARTNER","CATALOG_GOOD","CATALOG_SERVICE"}) {
                var config=await NumberingKernel.Read(db,tenant,entity);
                Require(config.Version==0 && config.NextNumber==1,"Default non valido");
                await NumberingKernel.Save(db,tenant,entity,config);
            }
            await tx.CommitAsync();
        }
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            Require(await BusinessPartnerNumbering.Allocate(db,tenant,null)=="BP-000001","Allocazione BP");
            Require((await NumberingKernel.Read(db,tenant,"CATALOG_GOOD")).NextNumber==1,"BP ha consumato GOOD");
            Require((await NumberingKernel.Read(db,tenant,"CATALOG_SERVICE")).Version==1,"BP ha aggiornato SERVICE");
            await tx.CommitAsync();
        }
        async Task<string> AllocateGood(int delay)
        {
            await using var db=Db();await using var tx=await db.Database.BeginTransactionAsync();
            var code=await NumberingKernel.Allocate(db,tenant,"CATALOG_GOOD",null);
            if(delay>0)await Task.Delay(delay);
            await tx.CommitAsync();return code;
        }
        var first=AllocateGood(200);await Task.Delay(50);var second=AllocateGood(0);
        var codes=await Task.WhenAll(first,second);
        Require(codes.Distinct().Count()==2 && codes.Contains("ART-000001") && codes.Contains("ART-000002"),"Allocazioni concorrenti non indipendenti");
        await using(var db=Db()) {
            await using(var tx=await db.Database.BeginTransactionAsync()) {
                Require(await NumberingKernel.Allocate(db,tenant,"CATALOG_GOOD",null)=="ART-000003","Progressivo prima rollback");
                await tx.RollbackAsync();
            }
            Require((await NumberingKernel.Read(db,tenant,"CATALOG_GOOD")).NextNumber==3,"Contatore non ripristinato dal rollback");
            await using var save=await db.Database.BeginTransactionAsync();
            var current=await NumberingKernel.Read(db,tenant,"CATALOG_SERVICE");
            await NumberingKernel.Save(db,tenant,"CATALOG_SERVICE",current with {Mode="MANUAL",Prefix="CUSTOM-",Padding=4});
            Require(await NumberingKernel.Allocate(db,tenant,"CATALOG_SERVICE","SERV-MANUAL")=="SERV-MANUAL","Codice manuale perso");
            Require((await NumberingKernel.Read(db,tenant,"CATALOG_SERVICE")).NextNumber==1,"Manuale ha consumato contatore");
            try {await NumberingKernel.Save(db,tenant,"CATALOG_SERVICE",(await NumberingKernel.Read(db,tenant,"CATALOG_SERVICE")) with {Prefix="NO"});throw new Exception("Modifica dopo utilizzo accettata");}
            catch(ApiException e) when(e.Code=="numbering_in_use") {}
            await save.CommitAsync();
        }
        var exhausted=Guid.NewGuid();
        await using(var db=Db()) {
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@id,@code,'Exhaustion proof')",("id",exhausted),("code",exhausted.ToString()));
            await using var tx=await db.Database.BeginTransactionAsync();
            await NumberingKernel.Save(db,exhausted,"CATALOG_GOOD",new("AUTO","ART-",6,NumberingKernel.Maximum,0));
            Require(await NumberingKernel.Allocate(db,exhausted,"CATALOG_GOOD",null)=="ART-999999999999999","Ultimo numero");
            try {await NumberingKernel.Allocate(db,exhausted,"CATALOG_GOOD",null);throw new Exception("Esaurimento non rifiutato");}
            catch(ApiException e) when(e.Code=="numbering_exhausted") {}
            await tx.CommitAsync();
        }
        Console.WriteLine("PASS numbering kernel: BP + GOOD + SERVICE independent, concurrent allocation, rollback, manual, exhaustion");
    }
}
