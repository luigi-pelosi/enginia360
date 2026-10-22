FROM quay.io/keycloak/keycloak:26.8.1@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244 AS build
ENV KC_DB=dev-file KC_HEALTH_ENABLED=true KC_HTTP_ENABLED=false
RUN /opt/keycloak/bin/kc.sh build
FROM quay.io/keycloak/keycloak:26.8.1@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244
COPY --from=build /opt/keycloak/ /opt/keycloak/
USER 1000:1000
