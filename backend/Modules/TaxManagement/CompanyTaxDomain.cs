using Enginia360.Shared.Validation;

namespace Enginia360.Modules.TaxManagement;

public sealed record CompanyTaxRegime(Guid Id,Guid CountryId,Guid TaxTypeId,string Code,bool IsActive,bool IsSupported,DateOnly ValidFrom,DateOnly? ValidTo);
public sealed record CompanyTaxRegimeProfile(Guid Id,Guid TaxRegimeId,DateOnly ValidFrom,DateOnly? ValidTo);
public sealed record CompanyTaxRegistration(Guid Id,Guid CountryId,string TaxIdentifier,string RegistrationType,DateOnly ValidFrom,DateOnly? ValidTo,string? Notes,IReadOnlyList<CompanyTaxRegimeProfile> Profiles);
public sealed record CompanyTaxContext(Guid TenantId,Guid CompanyId,Guid ConfigurationId,Guid TaxRegistrationId,Guid RegistrationCountryId,Guid TaxTypeId,Guid EstablishmentCountryId,string TaxIdentifier,string RegistrationType,Guid TaxRegimeProfileId,Guid TaxRegimeId,string TaxRegimeCode,DateOnly TaxDate);

/// <summary>Radice effettiva: identità immutabile, intervalli inclusivi, una revisione per comando.</summary>
public sealed class CompanyTaxConfiguration
{
    public Guid Id {get;}
    public Guid TenantId {get;}
    public Guid CompanyId {get;}
    public Guid TaxTypeId {get;}
    public Guid EstablishmentCountryId {get;}
    public string Status {get;private set;}
    public long Version {get;private set;}
    public string? TaxCode {get;private set;}
    private readonly List<CompanyTaxRegistration> registrations;
    public IReadOnlyList<CompanyTaxRegistration> Registrations=>registrations.AsReadOnly();
    public static void Require(bool ok,string code,int status=400,string? field=null)=>TaxRules.Require(ok,"company_tax_"+code,status,field);
    public static void Interval(DateOnly from,DateOnly? to)=>Require(to==null || to>=from,"invalid_interval",field:"valid_to");
    public static bool Covers(DateOnly from,DateOnly? to,DateOnly date)=>from<=date && (to==null || date<=to);
    public static bool Contains(DateOnly from,DateOnly? to,DateOnly childFrom,DateOnly? childTo)=>from<=childFrom && (to==null || childTo!=null && childTo<=to);
    public CompanyTaxConfiguration(Guid id,Guid tenant,Guid company,Guid type,Guid establishment,string status="DRAFT",long version=1,IEnumerable<CompanyTaxRegistration>? children=null,string? taxCode=null)
    {
        Require(new[]{id,tenant,company,type,establishment}.All(x=>x!=Guid.Empty),"invalid_id");
        Require(status is "DRAFT" or "ACTIVE" or "SUSPENDED","invalid_status");
        Require(version>=1 && version<=TaxRules.MaxRevision,"invalid_version");
        Id=id;TenantId=tenant;CompanyId=company;TaxTypeId=type;EstablishmentCountryId=establishment;Status=status;Version=version;
        registrations=children?.ToList()??[];
        TaxCode=NormalizeTaxCode(taxCode);
    }
    public static string? NormalizeTaxCode(string? value)
    {
        if(value==null)return null;
        Require(value.Length<=500,"field_too_long",field:"tax_code");
        Require(!value.Contains('\0'),"invalid_field",field:"tax_code");
        for(var i=0;i<value.Length;i++) {
            if(char.IsHighSurrogate(value[i])) {Require(i+1<value.Length && char.IsLowSurrogate(value[i+1]),"invalid_field",field:"tax_code");i++;}
            else Require(!char.IsLowSurrogate(value[i]),"invalid_field",field:"tax_code");
        }
        var text=value.Trim();return text.Length==0?null:text;
    }
    public void UpdateTaxCode(string? value,long expected)
    {
        CheckVersion(expected);var normalized=NormalizeTaxCode(value);TaxCode=normalized;Version++;
    }
    public void CheckVersion(long expected)
    {
        Require(expected>=1 && expected<=TaxRules.MaxRevision,"invalid_expected_version",field:"expectedVersion");
        Require(expected==Version,"stale_version",409,"expectedVersion");
        Require(Version<TaxRules.MaxRevision,"version_exhausted",409,"expectedVersion");
    }
    public CompanyTaxRegistration Registration(Guid id)=>registrations.SingleOrDefault(r=>r.Id==id)??throw new ApiException(404,"company_tax_registration_not_found","registrationId");
    public void ValidateRegistration(CompanyTaxRegistration next,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes,bool requireAssignable=true)
    {
        Interval(next.ValidFrom,next.ValidTo);
        Require(next.CountryId!=Guid.Empty && next.Id!=Guid.Empty,"invalid_id");
        Require(next.RegistrationType is "DOMESTIC" or "DIRECT_IDENTIFICATION" or "FISCAL_REPRESENTATIVE","invalid_registration_type",field:"registration_type");
        Require((next.RegistrationType=="DOMESTIC")== (next.CountryId==EstablishmentCountryId),"registration_type_country_mismatch",field:"registration_type");
        foreach(var existing in registrations.Where(x=>x.Id!=next.Id)) {
            var overlap=TaxRules.Overlaps(existing.ValidFrom,existing.ValidTo,next.ValidFrom,next.ValidTo);
            Require(!overlap || existing.CountryId!=next.CountryId || existing.TaxIdentifier!=next.TaxIdentifier,"identifier_overlap",409,"tax_identifier");
            Require(!overlap || existing.RegistrationType!="DOMESTIC" || next.RegistrationType!="DOMESTIC","domestic_overlap",409,"valid_from");
        }
        foreach(var p in next.Profiles)ValidateProfile(next,p,regimes,requireAssignable);
        for(var i=0;i<next.Profiles.Count;i++)for(var j=0;j<i;j++)
            Require(!TaxRules.Overlaps(next.Profiles[i].ValidFrom,next.Profiles[i].ValidTo,next.Profiles[j].ValidFrom,next.Profiles[j].ValidTo),"profile_overlap",409,"valid_from");
    }
    private void ValidateProfile(CompanyTaxRegistration registration,CompanyTaxRegimeProfile p,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes,bool requireAssignable)
    {
        Interval(p.ValidFrom,p.ValidTo);
        Require(Contains(registration.ValidFrom,registration.ValidTo,p.ValidFrom,p.ValidTo),"profile_registration_validity_mismatch",field:"valid_to");
        Require(regimes.TryGetValue(p.TaxRegimeId,out var regime),"regime_not_found",404,"tax_regime_id");
        Require(regime!.CountryId==registration.CountryId && regime.TaxTypeId==TaxTypeId,"regime_scope_mismatch",field:"tax_regime_id");
        Require(!requireAssignable || regime.IsActive && regime.IsSupported && regime.Code=="ORDINARY","regime_not_supported",409,"tax_regime_id");
        Require(Contains(regime.ValidFrom,regime.ValidTo,p.ValidFrom,p.ValidTo),"profile_regime_validity_mismatch",field:"valid_to");
    }
    public bool HasCoverage(DateOnly date,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)=>registrations.Any(r=>Covers(r.ValidFrom,r.ValidTo,date) && r.Profiles.Any(p=>Covers(p.ValidFrom,p.ValidTo,date) && regimes.TryGetValue(p.TaxRegimeId,out var g) && g.IsActive && g.IsSupported && g.Code=="ORDINARY" && g.CountryId==r.CountryId && g.TaxTypeId==TaxTypeId && Covers(g.ValidFrom,g.ValidTo,date)));
    private void GuardActive(DateOnly today,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)=>Require(Status!="ACTIVE" || HasCoverage(today,regimes),"active_coverage_required",409,"status");
    public void Initialize(IEnumerable<CompanyTaxRegistration> initial,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)
    {
        Require(Version==1 && Status=="DRAFT" && registrations.Count==0,"already_initialized",409);
        var entries=initial.ToArray();
        Require(entries.Length>0,"initial_registration_required",field:"registrations");
        Require(entries.All(r=>r.Profiles.Count>0),"initial_regime_required",field:"profiles");
        // Validate the complete proposed tree on a copy before mutating this aggregate.
        var proposed=new CompanyTaxConfiguration(Id,TenantId,CompanyId,TaxTypeId,EstablishmentCountryId);
        foreach(var r in entries){proposed.ValidateRegistration(r,regimes);proposed.registrations.Add(r);}
        registrations.AddRange(entries);
    }
    public void Register(CompanyTaxRegistration registration,long expected,DateOnly today,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)
    {
        CheckVersion(expected);
        Require(registration.Profiles.Count>0,"initial_regime_required",field:"profiles");
        ValidateRegistration(registration,regimes);
        var proposed=registrations.Append(registration).ToArray();
        var copy=new CompanyTaxConfiguration(Id,TenantId,CompanyId,TaxTypeId,EstablishmentCountryId,Status,Version,proposed);copy.GuardActive(today,regimes);
        registrations.Add(registration);Version++;
    }
    public void SetStatus(string status,long expected,DateOnly today,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)
    {
        CheckVersion(expected);Require(status is "ACTIVE" or "SUSPENDED","invalid_status",field:"status");
        Require(Status!=status,"invalid_transition",409,"status");
        Require(status!="ACTIVE" || HasCoverage(today,regimes),"activation_coverage_required",409,"status");
        Status=status;Version++;
    }
    public void Close(Guid registrationId,DateOnly end,long expected,DateOnly today,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)
    {
        CheckVersion(expected);var before=Registration(registrationId);Interval(before.ValidFrom,end);
        Require(before.ValidTo==null || end<before.ValidTo,"close_must_shorten",409,"valid_to");
        Require(!before.Profiles.Any(p=>p.ValidFrom>end),"close_future_profile",409,"valid_to");
        var next=before with {ValidTo=end,Profiles=before.Profiles.Select(p=>p.ValidTo==null || p.ValidTo>end?p with {ValidTo=end}:p).ToArray()};
        var copy=new CompanyTaxConfiguration(Id,TenantId,CompanyId,TaxTypeId,EstablishmentCountryId,Status,Version,registrations.Select(r=>r.Id==registrationId?next:r));copy.GuardActive(today,regimes);
        registrations[registrations.IndexOf(before)]=next;Version++;
    }
    public void AssignRegime(Guid registrationId,CompanyTaxRegimeProfile profile,long expected,bool schedule,DateOnly today,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)
    {
        CheckVersion(expected);var before=Registration(registrationId);ValidateProfile(before,profile,regimes,true);
        var covering=schedule?before.Profiles.Where(p=>p.ValidFrom<profile.ValidFrom && Covers(p.ValidFrom,p.ValidTo,profile.ValidFrom)).ToArray():[];
        Require(covering.Length<=1,"profile_overlap",409,"valid_from");var predecessor=covering.SingleOrDefault();
        var next=before with {Profiles=before.Profiles.Select(p=>p.Id==predecessor?.Id?p with {ValidTo=profile.ValidFrom.AddDays(-1)}:p).Append(profile).ToArray()};
        ValidateRegistration(next,regimes,false);
        var copy=new CompanyTaxConfiguration(Id,TenantId,CompanyId,TaxTypeId,EstablishmentCountryId,Status,Version,registrations.Select(r=>r.Id==registrationId?next:r));copy.GuardActive(today,regimes);
        registrations[registrations.IndexOf(before)]=next;Version++;
    }
    public CompanyTaxContext Resolve(Guid registrationId,DateOnly date,bool forNewUse,bool companyEnabled,IReadOnlyDictionary<Guid,CompanyTaxRegime> regimes)
    {
        Require(!forNewUse || companyEnabled && Status=="ACTIVE","not_eligible",409,"date");
        var registration=Registration(registrationId);
        Require(Covers(registration.ValidFrom,registration.ValidTo,date),"context_not_found",404,"date");
        var matches=registration.Profiles.Where(p=>Covers(p.ValidFrom,p.ValidTo,date) && regimes.TryGetValue(p.TaxRegimeId,out var g) && g.CountryId==registration.CountryId && g.TaxTypeId==TaxTypeId && Covers(g.ValidFrom,g.ValidTo,date)).ToArray();
        Require(matches.Length==1,"context_not_found",404,"date");var p=matches[0];var g=regimes[p.TaxRegimeId];
        Require(!forNewUse || g.IsActive && g.IsSupported && g.Code=="ORDINARY","regime_not_supported",409,"tax_regime_id");
        return new(TenantId,CompanyId,Id,registration.Id,registration.CountryId,TaxTypeId,EstablishmentCountryId,registration.TaxIdentifier,registration.RegistrationType,p.Id,g.Id,g.Code,date);
    }
}
