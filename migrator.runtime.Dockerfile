FROM postgres:18.0-alpine3.22@sha256:48c8ad3a7284b82be4482a52076d47d879fd6fb084a1cbfccbd551f9331b0e40
RUN apk add --no-cache python3=3.12.16-r0
WORKDIR /runtime
COPY scripts/apply-runtime-migrations.py scripts/test-r00-migrations.py scripts/test-r00b-bindings.py scripts/test-r01b-grants.py scripts/test-r02b-authority.py scripts/test-r03a-migration.py scripts/test-r04b1-supplier.py scripts/test-r04b2a-purchase.py scripts/test-r04b2b1-prices.py scripts/test-r04b2b2-freeze.py scripts/test-r04b2b3-dispatch.py scripts/owner-purchase-price-grant.py scripts/owner-master-authority.py scripts/owner-supplier-vendor-identity.py scripts/owner-operative-mandate.py scripts/validate-runtime-config.py ./scripts/
COPY database/runtime ./database/runtime
COPY src/Modules/Integrations/module.json ./src/Modules/Integrations/module.json
USER 70:70
ENTRYPOINT ["python3", "scripts/apply-runtime-migrations.py"]
