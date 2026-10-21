FROM postgres:18.0-alpine3.22@sha256:48c8ad3a7284b82be4482a52076d47d879fd6fb084a1cbfccbd551f9331b0e40
RUN apk add --no-cache python3=3.12.15-r0
COPY scripts/validate-runtime-config.py /runtime/validate-runtime-config.py
COPY database/runtime/bootstrap-roles.sh /docker-entrypoint-initdb.d/000_runtime_roles.sh
RUN chmod 0555 /docker-entrypoint-initdb.d/000_runtime_roles.sh
USER 70:70
