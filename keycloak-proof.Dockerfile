FROM quay.io/keycloak/keycloak:26.8.1@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244 AS builder
ENV KC_HEALTH_ENABLED=true \
    KC_DB=dev-file \
    KC_HTTP_ENABLED=true
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.8.1@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244
COPY --from=builder /opt/keycloak/ /opt/keycloak/
COPY --chown=1000:1000 keycloak/b02-realm.json /opt/keycloak/data/import/enginia360-synthetic-realm.json
