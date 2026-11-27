using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Text.Json;

namespace Enginia360.Verification.Shared;

public static class OptionalCodeSelfTests
{
    public static void Run(Action<string,Action> test)
    {
        foreach(var resource in ResourceCatalog.All.Values.Where(r => r.Fields.Any(f => f.Name == "name") && r.Fields.Any(f => f.Name == "code")))
            test("optional code: name precedes code in "+resource.Key,() => {
                var names=resource.Fields.Select(f => f.Name).ToArray();
                if(Array.IndexOf(names,"name") >= Array.IndexOf(names,"code") || names[0] == "code")
                    throw new Exception("Name must precede code; code must never be first: "+resource.Key);
            });
        test("optional code: company create needs only name",() => {
            var values=ResourceCatalog.Validate(ResourceCatalog.Get("companies"),JsonSerializer.SerializeToElement(new {name="Company"}),true);
            if(values.Count != 1 || !Equals(values["name"],"Company") || values.ContainsKey("code"))
                throw new Exception("Omitted code must stay omitted; no generated value.");
        });
        var optionalKeys=new[] {"companies","sales-organizations","purchasing-organizations","sites","warehouse-types","warehouses","warehouse-locations","groups","roles"};
        foreach(var key in optionalKeys)
        {
            var resource=ResourceCatalog.Get(key);
            Dictionary<string,object?> Payload(bool create)
            {
                var payload=new Dictionary<string,object?> { ["name"]="Example" };
                if(create && key=="sites") {
                    payload["address"]="Synthetic Road 42"; payload["city"]="Synthetic City";
                    payload["province"]="Synthetic Region"; payload["postal_code"]="AB 12-X"; payload["country_code"]="GB";
                }
                if(create) foreach(var field in resource.Fields.Where(f => f.Type == "reference" && f.Required))
                    payload[field.Name]="00000000-0000-0000-0000-000000000001";
                return payload;
            }
            test("optional code: blanks become null in "+key,() => {
                foreach(var create in new[]{true,false}) foreach(var blank in new[]{""," \t\n ","\u00a0\u2003"}) {
                    var payload=Payload(create); payload["code"]=blank;
                    if(ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(payload),create)["code"] != null)
                        throw new Exception("Blank code must become null.");
                }
            });
            test("optional code: supplied value trimmed in "+key,() => {
                foreach(var create in new[]{true,false}) {
                    var payload=Payload(create); payload["code"]=" \t É-李😀 \n";
                    if(!Equals(ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(payload),create)["code"],"É-李😀"))
                        throw new Exception("Supplied code must be trimmed, not generated or rewritten.");
                }
            });
            test("optional code: omitted and explicit null accepted in "+key,() => {
                foreach(var create in new[]{true,false}) {
                    var payload=Payload(create);
                    if(ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(payload),create).ContainsKey("code"))
                        throw new Exception("Omission must preserve the absence of code.");
                    payload["code"]=null;
                    if(ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(payload),create)["code"] != null)
                        throw new Exception("Explicit null must stay null.");
                }
            });
            test("optional code: limits types NUL and Unicode preserved in "+key,() => {
                foreach(var create in new[]{true,false}) {
                    foreach(var valid in new[]{new string('x',500),string.Concat(Enumerable.Repeat("😀",250)),"Stable-123"}) {
                        var payload=Payload(create); payload["code"]=valid;
                        if(!Equals(ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(payload),create)["code"],valid))
                            throw new Exception("Valid existing code changed.");
                    }
                    foreach(var invalid in new object[]{new string('x',501),new string(' ',501),"bad\0code",123,true,new[]{"code"}}) {
                        var payload=Payload(create); payload["code"]=invalid;
                        Reject(() => ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(payload),create));
                    }
                }
                foreach(var raw in new[]{"\"bad\\ud800value\"","\"bad\\udc00value\"","\"\\ud800\""})
                    Reject(() => ResourceCatalog.Validate(resource,JsonSerializer.Deserialize<JsonElement>("{\"code\":"+raw+"}"),false));
                Reject(() => ResourceCatalog.Validate(resource,JsonSerializer.Deserialize<JsonElement>("{\"code\":null,\"code\":null}"),false));
                Reject(() => ResourceCatalog.Validate(resource,JsonSerializer.SerializeToElement(new {code="x"}),true));
            });
        }
        test("optional code: required metadata exceptions and names preserved",() => {
            foreach(var resource in ResourceCatalog.All.Values) {
                foreach(var field in resource.Fields.Where(f => f.Name == "name"))
                    if(!field.Required) throw new Exception("Name must remain required: "+resource.Key);
                foreach(var field in resource.Fields.Where(f => f.Name == "code"))
                    if(field.Required != (resource.Key is "tenants" or "permissions" or "currencies"))
                        throw new Exception("Unexpected code requirement: "+resource.Key);
            }
            if(!ResourceCatalog.Get("permissions").ReadOnly) throw new Exception("Permission catalog must stay read-only.");
        });
        test("optional code: tenant code validation remains unchanged",() => {
            var tenant=ResourceCatalog.Get("tenants");
            foreach(var create in new[]{true,false}) {
                foreach(var invalid in new string?[]{null,""," \t\n "})
                    Reject(() => ResourceCatalog.Validate(tenant,JsonSerializer.SerializeToElement(new {name="Tenant",code=invalid}),create));
                var values=ResourceCatalog.Validate(tenant,JsonSerializer.SerializeToElement(new {name="Tenant",code=" T "}),create);
                if(!Equals(values["code"]," T ")) throw new Exception("Tenant code normalization changed.");
                Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("permissions"),JsonSerializer.SerializeToElement(new {name="Permission",code="system.read"}),create),403);
            }
            Reject(() => ResourceCatalog.Validate(tenant,JsonSerializer.SerializeToElement(new {name="Tenant"}),true));
        });
        test("optional code: unrelated code-like fields unchanged",() => {
            var values=ResourceCatalog.Validate(ResourceCatalog.Get("sites"),JsonSerializer.SerializeToElement(new {country_code="IT"}),false);
            if(!Equals(values["country_code"],"IT")) throw new Exception("Site country changed.");
            Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("sites"),JsonSerializer.SerializeToElement(new {country_code=" IT "}),false));

        });
    }

    static void Reject(Action run,int status=400)
    {
        try {run();} catch(ApiException e) when(e.Status == status && (status != 400 || e.Code == "validation_error")) {return;}
        throw new Exception("Expected controlled refusal: "+status);
    }
}
