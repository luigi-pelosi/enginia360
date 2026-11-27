using Enginia360.Shared.Validation;

namespace Enginia360.Modules.TaxManagement;

public sealed record ClassificationProfile(Guid Id,Guid CountryId,Guid TaxTypeId,Guid ClassificationId,DateOnly ValidFrom,DateOnly? ValidTo,long Revision);
public sealed record ClassificationProfilePlan(long Revision,Guid? PredecessorId,DateOnly? PredecessorValidTo);

/// <summary>Stream di revisioni del soggetto, indipendente dalle versioni Catalogo e Business Partner.</summary>
public sealed class ClassificationTimeline
{
    public const long MaxRevision=9007199254740991;
    private readonly ClassificationProfile[] profiles;
    public long Version => profiles.Select(x=>x.Revision).DefaultIfEmpty(0).Max();
    public ClassificationTimeline(IEnumerable<ClassificationProfile> existing)
    {
        profiles=existing.ToArray();
        foreach(var p in profiles) Validate(p);
        Require(profiles.Select(x=>x.Revision).Distinct().Count()==profiles.Length,"tax_profile_duplicate_revision",409,"revision");
        foreach(var scope in profiles.GroupBy(x=>(x.CountryId,x.TaxTypeId))) {
            var ordered=scope.OrderBy(x=>x.ValidFrom).ToArray();
            for(var i=1;i<ordered.Length;i++) Require(!Overlaps(ordered[i-1],ordered[i]),"tax_profile_overlap",409,"valid_from");
        }
    }
    public static void Require(bool condition,string code,int status=400,string? field=null)
    {if(!condition)throw new ApiException(status,code,field);}
    public static void CheckVersion(long expected,long actual,string prefix="tax_profile")
    {
        Require(expected>=0 && expected<=MaxRevision,prefix+"_invalid_expected_version",field:"expectedVersion");
        Require(expected==actual,prefix+"_stale_version",409,"expectedVersion");
        Require(actual<MaxRevision,prefix+"_version_exhausted",409,"expectedVersion");
    }
    public static void Validate(ClassificationProfile p)
    {
        Require(p.Id!=Guid.Empty && p.CountryId!=Guid.Empty && p.TaxTypeId!=Guid.Empty && p.ClassificationId!=Guid.Empty,"tax_profile_invalid_reference",field:"classification_id");
        Require(p.ValidTo==null || p.ValidTo>=p.ValidFrom,"tax_profile_invalid_interval",field:"valid_to");
        Require(p.Revision>=0 && p.Revision<=MaxRevision,"tax_profile_invalid_revision",field:"revision");
    }
    private static bool SameScope(ClassificationProfile a,ClassificationProfile b)=>a.CountryId==b.CountryId && a.TaxTypeId==b.TaxTypeId;
    public static bool Overlaps(ClassificationProfile a,ClassificationProfile b)=>a.ValidFrom<=(b.ValidTo??DateOnly.MaxValue) && b.ValidFrom<=(a.ValidTo??DateOnly.MaxValue);
    public ClassificationProfilePlan Plan(ClassificationProfile next,long expectedVersion,bool schedule)
    {
        CheckVersion(expectedVersion,Version);Validate(next);
        var scope=profiles.Where(x=>SameScope(x,next)).ToArray();
        var predecessor=schedule?scope.SingleOrDefault(x=>x.ValidFrom<next.ValidFrom && (x.ValidTo==null || x.ValidTo>=next.ValidFrom)):null;
        foreach(var p in scope.Where(x=>x.Id!=predecessor?.Id)) Require(!Overlaps(p,next),"tax_profile_overlap",409,"valid_from");
        return new(Version+1,predecessor?.Id,predecessor==null?null:next.ValidFrom.AddDays(-1));
    }
    public ClassificationProfile Resolve(Guid country,Guid taxType,DateOnly date)
        =>profiles.SingleOrDefault(x=>x.CountryId==country && x.TaxTypeId==taxType && x.ValidFrom<=date && (x.ValidTo==null || x.ValidTo>=date))??throw new ApiException(404,"tax_profile_not_found","date");
}

public sealed record TaxClassificationIdentity(Guid Id,Guid CountryId,Guid TaxTypeId,bool IsActive,bool SupportedType,long Version)
{
    public void RequireAssignable(Guid country,Guid type)
    {
        ClassificationTimeline.Require(CountryId==country,"tax_profile_classification_country_mismatch",field:"country_id");
        ClassificationTimeline.Require(TaxTypeId==type,"tax_profile_classification_type_mismatch",field:"tax_type_id");
        ClassificationTimeline.Require(IsActive,"tax_profile_classification_inactive",409,"classification_id");
        ClassificationTimeline.Require(SupportedType,"tax_classification_type_not_supported",409,"tax_type_id");
    }
    public void CheckMutation(long expected,bool reactivating=false)
    {
        ClassificationTimeline.CheckVersion(expected,Version,"tax_classification");
        ClassificationTimeline.Require(!reactivating || SupportedType,"tax_classification_type_not_supported",409,"tax_type_id");
    }
}
