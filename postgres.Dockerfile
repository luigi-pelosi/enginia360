FROM postgres:18.0-alpine3.22@sha256:48c8ad3a7284b82be4482a52076d47d879fd6fb084a1cbfccbd551f9331b0e40
COPY database/ /docker-entrypoint-initdb.d/
RUN chmod 0555 /docker-entrypoint-initdb.d/*.sh && mkdir -p /var/lib/postgresql/18/docker && chown -R postgres:postgres /var/lib/postgresql
